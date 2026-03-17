"""
Portfolio DevLog API
- 공개 API: 글 목록, 글 상세 조회, 사이트 콘텐츠 조회
- 관리자 API: 로그인, 글 CRUD, 사이트 콘텐츠 편집
"""
import os
import json
import uuid
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt

# Configuration
DATA_DIR = Path(os.getenv("DATA_DIR", "/data/posts"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

SITE_CONTENT_FILE = Path(os.getenv("DATA_DIR", "/data/posts")).parent / "site-content.json"
IMAGES_DIR = Path(os.getenv("DATA_DIR", "/data/posts")).parent / "images"

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

DEFAULT_SITE_CONTENT = {
    "profile": {
        "name": "Youngmin",
        "role": "DevOps / SRE Engineer",
        "bio": "Kubernetes, CI/CD, Infrastructure as Code 전문.\n안정적인 서비스 운영과 개발 생산성 향상에 관심이 많습니다.",
        "avatar_url": "/assets/images/증명.jpg",
        "blog_links": [
            {"title": "Tistory Blog", "url": "https://infra-for-prime.tistory.com/"},
            {"title": "Naver Blog", "url": "https://blog.naver.com/nim4042"}
        ]
    },
    "tech_stack": ["Kubernetes", "Docker", "Terraform", "ArgoCD", "NAVER Cloud Platform", "Python", "LLM", "AI"],
    "certifications": [],
    "featured_project": {
        "badge": "Live Demo",
        "title": "RAG 기반 AI 질의응답 시스템",
        "description": "K3s Kubernetes 환경에서 마이크로서비스로 운영되는 RAG(Retrieval-Augmented Generation) 시스템입니다. Qdrant 벡터 DB를 활용한 시맨틱 검색, HyperCLOVA X LLM을 통한 실시간 스트리밍 답변 생성, PDF/텍스트 문서 업로드 및 청킹, 폴더 기반 문서 관리 기능을 제공합니다.",
        "tech_tags": ["Python", "FastAPI", "Qdrant", "HyperCLOVA X", "K3s", "Docker", "Traefik"],
        "demo_link": "/rag"
    },
    "footer": {
        "copyright": "© 2025 youngmin's Cloud. Powered by Kubernetes."
    },
    "site": {
        "title": "youngmin's Cloud",
        "subtitle": "DevOps & Cloud Engineering Blog"
    }
}

app = FastAPI(
    title="Portfolio DevLog API",
    description="Development journey blog API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


# ============== Models ==============

class PostCreate(BaseModel):
    title: str
    content: str
    tags: List[str] = []
    published: bool = True


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    published: Optional[bool] = None


class Post(BaseModel):
    id: int
    slug: str
    title: str
    content: str
    tags: List[str]
    created_at: str
    updated_at: str
    published: bool


class PostSummary(BaseModel):
    id: int
    slug: str
    title: str
    excerpt: str
    tags: List[str]
    created_at: str
    published: bool


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_at: str


class BlogLink(BaseModel):
    title: str
    url: str


class Profile(BaseModel):
    name: str
    role: str
    bio: str
    avatar_url: str
    blog_links: List[BlogLink] = []


class Certification(BaseModel):
    name: str
    issuer: str
    date: str
    color: str


class FeaturedProject(BaseModel):
    badge: str
    title: str
    description: str
    tech_tags: List[str]
    demo_link: str


class Footer(BaseModel):
    copyright: str


class SiteInfo(BaseModel):
    title: str
    subtitle: str


class SiteContent(BaseModel):
    profile: Profile
    tech_stack: List[str]
    certifications: List[Certification]
    featured_project: FeaturedProject
    footer: Footer
    site: SiteInfo


# ============== Helpers ==============

def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title"""
    import re
    # 한글, 영문, 숫자만 유지
    slug = re.sub(r'[^\w\s가-힣-]', '', title.lower())
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = slug.strip('-')
    return slug[:50] if slug else str(uuid.uuid4())[:8]


def get_next_id() -> int:
    """Get next available post ID"""
    posts = load_all_posts()
    if not posts:
        return 1
    return max(p["id"] for p in posts) + 1


def load_all_posts() -> List[dict]:
    """Load all posts from disk"""
    posts = []
    if DATA_DIR.exists():
        for file_path in sorted(DATA_DIR.glob("*.json")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    posts.append(json.load(f))
            except Exception:
                continue
    return sorted(posts, key=lambda x: x.get("id", 0), reverse=True)


def save_post(post: dict) -> None:
    """Save post to disk"""
    file_name = f"{post['id']:03d}-{post['slug']}.json"
    file_path = DATA_DIR / file_name

    # Remove old file if slug changed
    for old_file in DATA_DIR.glob(f"{post['id']:03d}-*.json"):
        if old_file != file_path:
            old_file.unlink()

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)


def delete_post_file(post_id: int) -> bool:
    """Delete post file from disk"""
    for file_path in DATA_DIR.glob(f"{post_id:03d}-*.json"):
        file_path.unlink()
        return True
    return False


def load_site_content() -> dict:
    """Load site content from disk, return defaults if not found"""
    data = DEFAULT_SITE_CONTENT.copy()
    if SITE_CONTENT_FILE.exists():
        try:
            with open(SITE_CONTENT_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            data.update(saved)
        except Exception:
            pass
    # migrate: remove legacy categories, ensure certifications exists
    data.pop("categories", None)
    if "certifications" not in data:
        data["certifications"] = []
    return data


def save_site_content(content: dict) -> None:
    """Save site content to disk"""
    SITE_CONTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SITE_CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)


def get_post_by_id(post_id: int) -> Optional[dict]:
    """Get post by ID"""
    for file_path in DATA_DIR.glob(f"{post_id:03d}-*.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_post_by_slug(slug: str) -> Optional[dict]:
    """Get post by slug"""
    for file_path in DATA_DIR.glob("*.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            post = json.load(f)
            if post.get("slug") == slug:
                return post
    return None


def create_excerpt(content: str, max_length: int = 150) -> str:
    """Create excerpt from content"""
    # Remove markdown headers and formatting
    import re
    text = re.sub(r'#+ ', '', content)
    text = re.sub(r'\*\*|__', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'\n+', ' ', text)
    text = text.strip()

    if len(text) > max_length:
        return text[:max_length].rsplit(' ', 1)[0] + "..."
    return text


# ============== Auth ==============

def create_token(data: dict) -> tuple[str, datetime]:
    """Create JWT token"""
    expires = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode = data.copy()
    to_encode.update({"exp": expires})
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify JWT token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        return True
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


# ============== Public Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/posts", response_model=List[PostSummary])
async def list_posts(include_unpublished: bool = False):
    """List all published posts"""
    posts = load_all_posts()

    if not include_unpublished:
        posts = [p for p in posts if p.get("published", True)]

    return [
        PostSummary(
            id=p["id"],
            slug=p["slug"],
            title=p["title"],
            excerpt=create_excerpt(p["content"]),
            tags=p.get("tags", []),
            created_at=p["created_at"],
            published=p.get("published", True)
        )
        for p in posts
    ]


@app.get("/api/posts/{identifier}", response_model=Post)
async def get_post(identifier: str):
    """Get post by ID or slug"""
    # Try as ID first
    try:
        post_id = int(identifier)
        post = get_post_by_id(post_id)
    except ValueError:
        # Try as slug
        post = get_post_by_slug(identifier)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Don't show unpublished posts to public
    if not post.get("published", True):
        raise HTTPException(status_code=404, detail="Post not found")

    return Post(**post)


# ============== Admin Endpoints ==============

@app.post("/api/admin/login", response_model=LoginResponse)
async def admin_login(request: LoginRequest):
    """Admin login"""
    if request.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )

    token, expires = create_token({"sub": "admin"})
    return LoginResponse(
        token=token,
        expires_at=expires.isoformat()
    )


@app.get("/api/admin/posts", response_model=List[PostSummary])
async def admin_list_posts(_: bool = Depends(verify_token)):
    """List all posts including unpublished (admin only)"""
    posts = load_all_posts()
    return [
        PostSummary(
            id=p["id"],
            slug=p["slug"],
            title=p["title"],
            excerpt=create_excerpt(p["content"]),
            tags=p.get("tags", []),
            created_at=p["created_at"],
            published=p.get("published", True)
        )
        for p in posts
    ]


@app.get("/api/admin/posts/{post_id}", response_model=Post)
async def admin_get_post(post_id: int, _: bool = Depends(verify_token)):
    """Get post by ID (admin only, includes unpublished)"""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return Post(**post)


@app.post("/api/admin/posts", response_model=Post)
async def create_post(post_data: PostCreate, _: bool = Depends(verify_token)):
    """Create new post (admin only)"""
    now = datetime.utcnow().isoformat() + "Z"

    post = {
        "id": get_next_id(),
        "slug": generate_slug(post_data.title),
        "title": post_data.title,
        "content": post_data.content,
        "tags": post_data.tags,
        "created_at": now,
        "updated_at": now,
        "published": post_data.published
    }

    save_post(post)
    return Post(**post)


@app.put("/api/admin/posts/{post_id}", response_model=Post)
async def update_post(post_id: int, post_data: PostUpdate, _: bool = Depends(verify_token)):
    """Update post (admin only)"""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Update fields
    if post_data.title is not None:
        post["title"] = post_data.title
        post["slug"] = generate_slug(post_data.title)
    if post_data.content is not None:
        post["content"] = post_data.content
    if post_data.tags is not None:
        post["tags"] = post_data.tags
    if post_data.published is not None:
        post["published"] = post_data.published

    post["updated_at"] = datetime.utcnow().isoformat() + "Z"

    save_post(post)
    return Post(**post)


@app.delete("/api/admin/posts/{post_id}")
async def delete_post(post_id: int, _: bool = Depends(verify_token)):
    """Delete post (admin only)"""
    if not delete_post_file(post_id):
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted"}


@app.get("/api/admin/verify")
async def verify_auth(_: bool = Depends(verify_token)):
    """Verify authentication token"""
    return {"valid": True}


# ============== Site Content Endpoints ==============

@app.get("/api/site-content")
async def get_site_content():
    """Get site content (public)"""
    return load_site_content()


@app.get("/api/admin/site-content")
async def admin_get_site_content(_: bool = Depends(verify_token)):
    """Get site content for editing (admin only)"""
    return load_site_content()


@app.put("/api/admin/site-content")
async def admin_update_site_content(content: SiteContent, _: bool = Depends(verify_token)):
    """Update site content (admin only)"""
    save_site_content(content.model_dump())
    return content


# ============== Image Endpoints ==============

@app.post("/api/admin/images")
async def upload_image(file: UploadFile = File(...), _: bool = Depends(verify_token)):
    """Upload an image for use in posts (admin only)"""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="허용된 이미지 형식: jpg, png, gif, webp"
        )

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="이미지 크기는 10MB 이하여야 합니다")

    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
    ext = ext_map.get(content_type, ".jpg")
    filename = f"{uuid.uuid4().hex}{ext}"

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    with open(IMAGES_DIR / filename, "wb") as f:
        f.write(content)

    return {"url": f"/devlog/api/images/{filename}", "filename": filename}


@app.get("/api/images/{filename}")
async def serve_image(filename: str):
    """Serve uploaded image (public)"""
    # Prevent path traversal
    safe_name = Path(filename).name
    file_path = IMAGES_DIR / safe_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(file_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
