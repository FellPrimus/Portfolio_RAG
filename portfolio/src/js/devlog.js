/**
 * DevLog - Public Blog JavaScript
 */

const API_BASE = '/devlog/api';

// Configure marked for syntax highlighting
marked.setOptions({
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true,
    gfm: true
});

// State
let posts = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadSiteContent();

    const urlParams = new URLSearchParams(window.location.search);
    const postId = urlParams.get('post');

    if (postId) {
        loadPostDetail(postId);
    } else {
        loadPosts();
    }
});

// Load site content for sidebar
async function loadSiteContent() {
    try {
        const response = await fetch(`${API_BASE}/site-content`);
        if (!response.ok) return;
        const sc = await response.json();

        // Profile
        const nameEl = document.getElementById('profile-name');
        const roleEl = document.getElementById('profile-role');
        const bioEl = document.getElementById('profile-bio');
        const avatarEl = document.getElementById('profile-avatar');
        if (nameEl) nameEl.textContent = sc.profile.name;
        if (roleEl) roleEl.textContent = sc.profile.role;
        if (bioEl) bioEl.textContent = sc.profile.bio;
        if (avatarEl) { avatarEl.src = sc.profile.avatar_url; avatarEl.alt = sc.profile.name; }

        // Tech Stack
        const techEl = document.getElementById('tech-tags');
        if (techEl && sc.tech_stack) {
            techEl.innerHTML = sc.tech_stack.map(t =>
                `<span class="tech-tag">${escapeHtml(t)}</span>`
            ).join('');
        }

        // Certifications
        const certCard = document.getElementById('cert-card');
        const certList = document.getElementById('cert-list');
        if (certCard && certList && sc.certifications && sc.certifications.length > 0) {
            certList.innerHTML = sc.certifications.map(c => `
                <li class="cert-item">
                    <span class="cert-dot" style="color: ${escapeHtml(c.color)};">&#9679;</span>
                    <div class="cert-info">
                        <span class="cert-name">${escapeHtml(c.name)}</span>
                        <span class="cert-meta">${escapeHtml(c.issuer)} · ${escapeHtml(c.date)}</span>
                    </div>
                </li>
            `).join('');
            certCard.style.display = '';
        }
    } catch (error) {
        console.error('Error loading site content:', error);
    }
}

// Load all posts
async function loadPosts() {
    const container = document.getElementById('posts-container');
    const countEl = document.getElementById('devlog-count');

    try {
        const response = await fetch(`${API_BASE}/posts`);

        if (!response.ok) {
            throw new Error('Failed to fetch posts');
        }

        posts = await response.json();

        // Update post count in sidebar
        if (countEl) {
            countEl.textContent = posts.length;
        }

        if (posts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>아직 작성된 글이 없습니다</h3>
                    <p>곧 개발 과정에 대한 이야기를 들려드릴게요.</p>
                </div>
            `;
            return;
        }

        renderPosts(posts);

    } catch (error) {
        console.error('Error loading posts:', error);
        container.innerHTML = `
            <div class="empty-state">
                <h3>글을 불러올 수 없습니다</h3>
                <p>잠시 후 다시 시도해주세요.</p>
            </div>
        `;
    }
}

// Render post list
function renderPosts(posts) {
    const container = document.getElementById('posts-container');

    container.innerHTML = posts.map((post, index) => `
        <article class="post-card" onclick="navigateToPost(${post.id})">
            <div class="post-number">#${post.id}</div>
            <h2 class="post-card-title">${escapeHtml(post.title)}</h2>
            <p class="post-card-excerpt">${escapeHtml(post.excerpt)}</p>
            <div class="post-card-footer">
                <div class="post-card-tags">
                    ${post.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                </div>
            </div>
        </article>
    `).join('');
}

// Navigate to post detail
function navigateToPost(postId) {
    window.history.pushState({}, '', `/devlog?post=${postId}`);
    loadPostDetail(postId);
}

// Load post detail
async function loadPostDetail(postId) {
    const listSection = document.getElementById('post-list');
    const detailSection = document.getElementById('post-detail');

    try {
        const response = await fetch(`${API_BASE}/posts/${postId}`);

        if (!response.ok) {
            if (response.status === 404) {
                alert('글을 찾을 수 없습니다.');
                window.location.href = '/devlog';
                return;
            }
            throw new Error('Failed to fetch post');
        }

        const post = await response.json();

        // Update page title
        document.title = `${post.title} - DevLog`;

        // Render post detail
        document.getElementById('detail-title').textContent = post.title;
        document.getElementById('detail-tags').innerHTML = post.tags
            .map(tag => `<span class="tag">${escapeHtml(tag)}</span>`)
            .join('');
        document.getElementById('detail-content').innerHTML = marked.parse(post.content);

        // Apply syntax highlighting to code blocks
        document.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });

        // Show detail, hide list
        listSection.style.display = 'none';
        detailSection.style.display = 'block';

        // Scroll to top
        window.scrollTo(0, 0);

    } catch (error) {
        console.error('Error loading post:', error);
        alert('글을 불러올 수 없습니다.');
        window.location.href = '/devlog';
    }
}

// Handle browser back button
window.addEventListener('popstate', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const postId = urlParams.get('post');

    if (postId) {
        loadPostDetail(postId);
    } else {
        // Show list, hide detail
        document.getElementById('post-list').style.display = 'block';
        document.getElementById('post-detail').style.display = 'none';
        document.title = 'DevLog - youngmin\'s Cloud';
        loadPosts();
    }
});

// Utility functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
