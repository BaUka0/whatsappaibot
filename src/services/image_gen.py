"""
Image generation service using Pollinations.ai
Free, no API key required!
https://pollinations.ai/llms.txt

Supports:
- Direct URL generation (no download needed)
- Multiple models: flux, turbo, nanobanana
- Prompt enhancement via LLM
"""
import httpx
import os
import random
import time
import logging
from urllib.parse import quote
from src.config import settings

logger = logging.getLogger(__name__)


# Prompt for enhancing user's image description
ENHANCE_PROMPT_SYSTEM = """You are an expert prompt engineer for AI image generation.

Transform the user's description into a detailed prompt for Stable Diffusion/Flux.

Rules:
1. Output ONLY the enhanced prompt, nothing else
2. Keep it under 100 words
3. Add style, lighting, composition details
4. Always use English
5. Add quality tags: detailed, high quality, 4k, masterpiece
6. Include artistic style (photorealistic, digital art, anime, etc.)

Example: "кот в космосе" → "A majestic cat floating in space, astronaut helmet, surrounded by colorful nebulas and distant galaxies, cosmic dust particles, cinematic lighting, hyperrealistic, 4k, detailed fur, vibrant cosmic colors, digital art masterpiece"
"""


async def enhance_prompt(user_prompt: str, model: str | None = None) -> str:
    """
    Enhance prompt using LLM for better image generation results.
    Falls back to original prompt on error.
    
    Args:
        user_prompt: Original user prompt
        model: LLM model to use (uses default if None)
    """
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
        
        # Use provided model or default
        use_model = model or settings.OPENROUTER_MODEL
        
        response = await client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": ENHANCE_PROMPT_SYSTEM},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        
        enhanced = response.choices[0].message.content.strip()
        # Remove quotes if present
        enhanced = enhanced.strip('"\'')
        logger.debug(f"[ImageGen] Enhanced prompt: {enhanced[:80]}...")
        return enhanced
        
    except Exception as e:
        logger.warning(f"[ImageGen] Enhancement failed: {e}, using original")
        return user_prompt


def build_pollinations_url(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    model: str = "flux",
    seed: int | None = None,
    nologo: bool = True
) -> str:
    """
    Build Pollinations.ai image URL.
    
    Models available:
    - flux: High quality (default)
    - turbo: Fast generation
    - nanobanana: Google Vertex AI (seed tier required)
    
    Note: URL doesn't need download - Green API can send directly via SendFileByUrl
    """
    # Clean and encode prompt
    clean_prompt = prompt.strip()
    # Use simple encoding - Pollinations handles it
    encoded_prompt = quote(clean_prompt, safe='')
    
    # Generate seed if not provided
    if seed is None:
        seed = random.randint(1, 999999)
    
    # Build URL with only alphanumeric params in URL
    # Format: https://image.pollinations.ai/prompt/{prompt}?params
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
    
    params = []
    params.append(f"width={width}")
    params.append(f"height={height}")
    params.append(f"model={model}")
    params.append(f"seed={seed}")
    if nologo:
        params.append("nologo=true")
    
    full_url = url + "?" + "&".join(params)
    
    return full_url, seed


async def verify_image_url(url: str, timeout: int = 90) -> tuple[bool, bytes | None]:
    """
    Verify that the image URL returns valid image data.
    Pollinations generates on-demand, so first request triggers generation.
    
    Returns:
        (is_valid, image_bytes or None)
    """
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"[ImageGen] Requesting image from Pollinations...")
            response = await client.get(
                url, 
                timeout=timeout, 
                follow_redirects=True
            )
            
            if response.status_code != 200:
                logger.error(f"[ImageGen] HTTP error: {response.status_code}")
                return False, None
            
            content_type = response.headers.get("content-type", "")
            if "image" not in content_type:
                logger.error(f"[ImageGen] Not an image: {content_type}")
                return False, None
            
            content = response.content
            if len(content) < 1000:
                logger.warning(f"[ImageGen] Image too small: {len(content)} bytes")
                return False, None
            
            logger.info(f"[ImageGen] Valid image received: {len(content)} bytes")
            return True, content
            
        except httpx.TimeoutException:
            logger.warning(f"[ImageGen] Timeout after {timeout}s")
            return False, None
        except Exception as e:
            logger.error(f"[ImageGen] Request error: {e}")
            return False, None


async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    model: str = "flux",
    enhance: bool = True,
    llm_model: str | None = None
) -> tuple[str | None, str, int | None]:
    """
    Generate image using Pollinations.ai
    
    This function:
    1. Enhances prompt with LLM (optional)
    2. Builds Pollinations URL
    3. Verifies the image is generated
    4. Saves locally for upload
    
    Args:
        prompt: Image description (any language)
        width: Image width (default 1024)
        height: Image height (default 1024)
        model: flux (default), turbo, or nanobanana
        enhance: Use LLM to improve prompt
        llm_model: LLM model for prompt enhancement (uses default if None)
    
    Returns:
        (file_path, final_prompt, seed) or (None, final_prompt, None) on error
    """
    # Step 1: Enhance prompt
    final_prompt = await enhance_prompt(prompt, model=llm_model) if enhance else prompt
    
    # Step 2: Build URL 
    image_url, seed = build_pollinations_url(
        prompt=final_prompt,
        width=width,
        height=height,
        model=model
    )
    
    logger.info(f"[ImageGen] URL: {image_url[:100]}...")
    logger.info(f"[ImageGen] Model: {model}, Seed: {seed}")
    
    # Step 3: Verify and download image
    is_valid, image_bytes = await verify_image_url(image_url)
    
    if not is_valid or image_bytes is None:
        logger.error("[ImageGen] Failed to generate image")
        return None, final_prompt, None
    
    # Step 4: Save to file
    timestamp = int(time.time())
    file_name = f"pollinations_{seed}_{timestamp}.png"
    file_path = os.path.join(settings.MEDIA_DIR, file_name)
    
    try:
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        logger.info(f"[ImageGen] Saved: {file_path} ({len(image_bytes)} bytes)")
        return file_path, final_prompt, seed
    except Exception as e:
        logger.error(f"[ImageGen] Failed to save file: {e}")
        return None, final_prompt, None


async def generate_and_get_url(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    model: str = "flux",
    enhance: bool = True
) -> tuple[str | None, str, int | None]:
    """
    Generate image and return the Pollinations URL.
    
    This is useful for SendFileByUrl method, but note:
    - Pollinations URLs contain special characters (?=&) which Green API doesn't like
    - Better to download and use SendFileByUpload
    
    Returns:
        (image_url, final_prompt, seed) or (None, final_prompt, None) on error
    """
    # Enhance prompt
    final_prompt = await enhance_prompt(prompt) if enhance else prompt
    
    # Build URL
    image_url, seed = build_pollinations_url(
        prompt=final_prompt,
        width=width,
        height=height,
        model=model
    )
    
    # Verify the image generates correctly
    is_valid, _ = await verify_image_url(image_url)
    
    if not is_valid:
        return None, final_prompt, None
    
    return image_url, final_prompt, seed
