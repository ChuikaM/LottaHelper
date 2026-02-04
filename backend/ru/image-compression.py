import os
import io
import sys
from typing import Union, Optional
from PIL import Image, ImageOps, ImageEnhance
import img2pdf
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None

def compress_image(
    img: Union[str, bytes, Image.Image],
    max_dimension: int = 1024,
    quality: int = 85,
    target_kb: Optional[int] = 1024,
    format: Optional[str] = None
) -> bytes:
    """
    Compress image/PDF for LLM usage with intelligent size optimization.
    
    Args:
        img: Path to file, bytes, or PIL Image
        max_dimension: Maximum width/height in pixels (maintains aspect ratio)
        quality: JPEG/WebP quality (1-95). Ignored for PNG.
        target_kb: Target file size in KB. Function will iteratively reduce quality to meet this.
        format: Output format ('JPEG', 'PNG', 'WEBP'). Auto-detected if None.
    
    Returns:
        Compressed image as bytes (optimized for LLM vision APIs)
    
    Supported inputs: PNG, JPG/JPEG, WEBP, PDF (first page converted to image)
    """
    # Step 1: Normalize input to PIL Image
    pil_img = _load_image(img)
    
    # Step 2: Resize while preserving aspect ratio
    pil_img = _resize_image(pil_img, max_dimension)
    
    # Step 3: Convert to efficient format
    output_format, pil_img = _optimize_format(pil_img, format)
    
    # Step 4: Iterative compression to hit target size
    compressed_bytes = _iterative_compress(
        pil_img, 
        output_format, 
        initial_quality=quality,
        target_bytes=target_kb * 1024 if target_kb else None
    )
    
    return compressed_bytes


def _load_image(img: Union[str, bytes, Image.Image]) -> Image.Image:
    """Normalize input to PIL Image. For PDFs, extract first page as image."""
    if isinstance(img, Image.Image):
        return img.convert("RGB") if img.mode in ("RGBA", "P") else img
    
    if isinstance(img, str):
        if not os.path.exists(img):
            raise FileNotFoundError(f"File not found: {img}")
        ext = os.path.splitext(img)[1].lower()
        if ext == ".pdf" and PdfReader:
            return _pdf_to_image(img)
        return Image.open(img).convert("RGB")
    
    if isinstance(img, bytes):
        try:
            # Try as image first
            return Image.open(io.BytesIO(img)).convert("RGB")
        except Exception:
            # Try as PDF
            if PdfReader:
                return _pdf_to_image(io.BytesIO(img))
            raise ValueError("Bytes input is not a valid image or PDF")
    
    raise TypeError(f"Unsupported input type: {type(img)}")


def _pdf_to_image(pdf_input) -> Image.Image:
    """Convert first page of PDF to RGB image using pdf2image (fallback to pypdf extraction)."""
    try:
        from pdf2image import convert_from_bytes, convert_from_path
        
        if isinstance(pdf_input, bytes):
            images = convert_from_bytes(pdf_input, dpi=100, first_page=1, last_page=1)
        else:
            images = convert_from_path(pdf_input, dpi=100, first_page=1, last_page=1)
        
        if not images:
            raise ValueError("No pages found in PDF")
        return images[0].convert("RGB")
    
    except ImportError:
        # Fallback: Extract images from PDF using pypdf (less reliable)
        if not PdfReader:
            raise ImportError(
                "PDF processing requires 'pdf2image' (recommended) or 'pypdf'. "
                "Install with: pip install pdf2image pypdf"
            )
        
        reader = PdfReader(pdf_input if isinstance(pdf_input, str) else io.BytesIO(pdf_input))
        if not reader.pages:
            raise ValueError("PDF has no pages")
        
        # Extract first image found on first page
        for img in reader.pages[0].images:
            return Image.open(io.BytesIO(img.data)).convert("RGB")
        
        # If no images, render page as blank (user should install pdf2image)
        raise ValueError("No images found in PDF. Install 'pdf2image' for reliable rendering.")


def _resize_image(img: Image.Image, max_dimension: int) -> Image.Image:
    """Resize image to fit within max_dimension while preserving aspect ratio."""
    if max(img.width, img.height) <= max_dimension:
        return img
    
    ratio = max_dimension / max(img.width, img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    return img.resize(new_size, Image.LANCZOS)


def _optimize_format(img: Image.Image, requested_format: Optional[str]) -> tuple[str, Image.Image]:
    """Convert to most efficient format for LLMs."""
    # Force RGB for JPEG/WebP compatibility
    if img.mode in ("RGBA", "P", "LA"):
        # Use white background for transparency
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    
    # Determine optimal format
    if requested_format:
        fmt = requested_format.upper()
    else:
        # Prefer WebP if available (best compression), fallback to JPEG
        fmt = "WEBP" if hasattr(Image, "WEBP") else "JPEG"
    
    return fmt, img


def _iterative_compress(
    img: Image.Image, 
    fmt: str, 
    initial_quality: int, 
    target_bytes: Optional[int]
) -> bytes:
    """Compress with iterative quality reduction to hit target file size."""
    buffer = io.BytesIO()
    
    # Fast path: try initial quality first
    save_kwargs = {"format": fmt, "optimize": True}
    if fmt in ("JPEG", "WEBP"):
        save_kwargs["quality"] = initial_quality
    
    img.save(buffer, **save_kwargs)
    size = buffer.tell()
    
    # If under target or no target specified, return immediately
    if not target_bytes or size <= target_bytes:
        return buffer.getvalue()
    
    # Iteratively reduce quality until under target
    quality = initial_quality
    while quality >= 40 and size > target_bytes:
        quality -= 10
        buffer = io.BytesIO()
        save_kwargs["quality"] = max(quality, 1)
        img.save(buffer, **save_kwargs)
        size = buffer.tell()
    
    # Last resort: convert to grayscale if still too large
    if size > target_bytes and fmt == "JPEG":
        gray = img.convert("L")
        buffer = io.BytesIO()
        gray.save(buffer, format="JPEG", quality=60, optimize=True)
        if buffer.tell() < size:
            return buffer.getvalue()
    
    return buffer.getvalue()