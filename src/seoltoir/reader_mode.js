/**
 * Seoltoir Reader Mode JavaScript Library
 * Article extraction and reading time calculation
 * Based on Mozilla's Readability.js algorithm
 */

class SeoltoirReaderMode {
    constructor() {
        this.UNLIKELY_CANDIDATES = /banner|breadcrumbs|combx|comment|community|cover-wrap|disqus|extra|foot|header|legends|menu|modal|related|remark|replies|rss|shoutbox|sidebar|skyscraper|social|sponsor|supplemental|ad-break|agegate|pagination|pager|popup|yom-remote/i;
        this.POSITIVE_CANDIDATES = /article|body|content|entry|hentry|h-entry|main|page|pagination|post|text|blog|story/i;
        this.NEGATIVE_CANDIDATES = /hidden|^hid$|hid$|hid|^hid |banner|combx|comment|com-|contact|foot|footer|footnote|masthead|media|meta|modal|outbrain|promo|related|scroll|share|shoutbox|sidebar|skyscraper|sponsor|shopping|tags|tool|widget/i;
        this.CONTENT_SELECTORS = [
            'article', 
            '[role="main"]', 
            'main', 
            '.content', 
            '.post-content', 
            '.entry-content', 
            '.article-content',
            '.story-content',
            '.post-body',
            '.entry-body'
        ];
        
        this.WORDS_PER_MINUTE = 200; // Average reading speed
        this.isReaderModeActive = false;
        this.originalContent = null;
        this.readerContent = null;
    }

    /**
     * Check if the current page is suitable for reader mode
     * @returns {boolean} true if reader mode can be applied
     */
    isReadable() {
        const textLength = this.getTextLength();
        const hasArticle = this.hasArticleContent();
        const hasMainContent = this.hasMainContent();
        
        return textLength > 500 && (hasArticle || hasMainContent);
    }

    /**
     * Get the total text length of the page
     */
    getTextLength() {
        const text = document.body.innerText || document.body.textContent || '';
        return text.trim().length;
    }

    /**
     * Check if page has article-like content
     */
    hasArticleContent() {
        return !!(document.querySelector('article') || 
                 document.querySelector('[role="main"]') ||
                 document.querySelector('.article') ||
                 document.querySelector('.post'));
    }

    /**
     * Check if page has main content area
     */
    hasMainContent() {
        return !!(document.querySelector('main') || 
                 document.querySelector('.content') ||
                 document.querySelector('.main-content'));
    }

    /**
     * Extract the main article content from the page
     * @returns {Object} extracted content with title, content, and metadata
     */
    extractArticle() {
        const article = this.findArticleContent();
        if (!article) {
            return null;
        }

        const title = this.extractTitle();
        const content = this.cleanContent(article);
        const wordCount = this.countWords(content);
        const readingTime = this.calculateReadingTime(wordCount);
        const author = this.extractAuthor();
        const publishDate = this.extractPublishDate();

        return {
            title,
            content,
            wordCount,
            readingTime,
            author,
            publishDate,
            url: window.location.href
        };
    }

    /**
     * Find the main article content on the page
     */
    findArticleContent() {
        // Try explicit content selectors first
        for (const selector of this.CONTENT_SELECTORS) {
            const element = document.querySelector(selector);
            if (element && this.getTextLength(element) > 300) {
                return element;
            }
        }

        // Score all paragraphs and find the best content container
        const allParagraphs = document.querySelectorAll('p');
        const candidates = new Map();

        allParagraphs.forEach(paragraph => {
            const parentNode = paragraph.parentNode;
            const grandParentNode = parentNode ? parentNode.parentNode : null;

            if (!parentNode || parentNode.tagName === 'BLOCKQUOTE') {
                return;
            }

            const innerText = paragraph.innerText.trim();
            if (innerText.length < 25) {
                return;
            }

            let score = 1;
            score += innerText.split(',').length;
            score += Math.min(Math.floor(innerText.length / 100), 3);

            if (!candidates.has(parentNode)) {
                candidates.set(parentNode, this.initializeNodeScore(parentNode));
            }
            candidates.set(parentNode, candidates.get(parentNode) + score);

            if (grandParentNode) {
                if (!candidates.has(grandParentNode)) {
                    candidates.set(grandParentNode, this.initializeNodeScore(grandParentNode));
                }
                candidates.set(grandParentNode, candidates.get(grandParentNode) + score / 2);
            }
        });

        // Find the candidate with the highest score
        let bestCandidate = null;
        let bestScore = 0;

        candidates.forEach((score, node) => {
            if (score > bestScore) {
                bestScore = score;
                bestCandidate = node;
            }
        });

        return bestCandidate;
    }

    /**
     * Initialize the score for a node based on its tag and class
     */
    initializeNodeScore(node) {
        let score = 0;
        
        switch (node.tagName.toLowerCase()) {
            case 'div':
                score += 5;
                break;
            case 'pre':
            case 'td':
            case 'blockquote':
                score += 3;
                break;
            case 'address':
            case 'ol':
            case 'ul':
            case 'dl':
            case 'dd':
            case 'dt':
            case 'li':
            case 'form':
                score -= 3;
                break;
            case 'h1':
            case 'h2':
            case 'h3':
            case 'h4':
            case 'h5':
            case 'h6':
            case 'th':
                score -= 5;
                break;
        }

        const className = node.className || '';
        const id = node.id || '';
        const classAndId = (className + ' ' + id).toLowerCase();

        if (this.POSITIVE_CANDIDATES.test(classAndId)) {
            score += 25;
        }

        if (this.UNLIKELY_CANDIDATES.test(classAndId)) {
            score -= 25;
        }

        if (this.NEGATIVE_CANDIDATES.test(classAndId)) {
            score -= 25;
        }

        return score;
    }

    /**
     * Clean the extracted content
     */
    cleanContent(element) {
        const clonedElement = element.cloneNode(true);
        
        // Remove unwanted elements
        const unwantedSelectors = [
            'script', 'style', 'nav', 'header', 'footer', 'aside',
            '.sidebar', '.navigation', '.menu', '.ads', '.advertisement',
            '.social', '.share', '.comments', '.related', '.pagination',
            '[class*="ad"]', '[id*="ad"]', '[class*="social"]', '[id*="social"]'
        ];
        
        unwantedSelectors.forEach(selector => {
            const unwantedElements = clonedElement.querySelectorAll(selector);
            unwantedElements.forEach(elem => elem.remove());
        });

        // Clean up attributes
        const allElements = clonedElement.querySelectorAll('*');
        allElements.forEach(elem => {
            // Keep only essential attributes
            const allowedAttributes = ['href', 'src', 'alt', 'title'];
            const attributes = Array.from(elem.attributes);
            attributes.forEach(attr => {
                if (!allowedAttributes.includes(attr.name)) {
                    elem.removeAttribute(attr.name);
                }
            });
        });

        // Ensure images have alt text
        const images = clonedElement.querySelectorAll('img');
        images.forEach(img => {
            if (!img.alt) {
                img.alt = 'Image';
            }
        });

        return clonedElement.innerHTML;
    }

    /**
     * Extract the title of the article
     */
    extractTitle() {
        // Try different title selectors
        const titleSelectors = [
            'h1',
            '.title',
            '.headline',
            '.article-title',
            '.post-title',
            '.entry-title',
            '[property="og:title"]',
            'title'
        ];

        for (const selector of titleSelectors) {
            const element = document.querySelector(selector);
            if (element) {
                const title = element.textContent || element.getAttribute('content');
                if (title && title.trim().length > 0) {
                    return title.trim();
                }
            }
        }

        return document.title || 'Article';
    }

    /**
     * Extract the author of the article
     */
    extractAuthor() {
        const authorSelectors = [
            '[rel="author"]',
            '.author',
            '.byline',
            '.by-author',
            '[property="article:author"]',
            '[name="author"]'
        ];

        for (const selector of authorSelectors) {
            const element = document.querySelector(selector);
            if (element) {
                const author = element.textContent || element.getAttribute('content');
                if (author && author.trim().length > 0) {
                    return author.trim();
                }
            }
        }

        return null;
    }

    /**
     * Extract the publish date of the article
     */
    extractPublishDate() {
        const dateSelectors = [
            '[property="article:published_time"]',
            '[property="datePublished"]',
            '.date',
            '.published',
            '.publish-date',
            'time[datetime]'
        ];

        for (const selector of dateSelectors) {
            const element = document.querySelector(selector);
            if (element) {
                const date = element.getAttribute('datetime') || 
                            element.getAttribute('content') || 
                            element.textContent;
                if (date && date.trim().length > 0) {
                    return date.trim();
                }
            }
        }

        return null;
    }

    /**
     * Count words in HTML content
     */
    countWords(htmlContent) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = htmlContent;
        const text = tempDiv.textContent || tempDiv.innerText || '';
        return text.trim().split(/\s+/).length;
    }

    /**
     * Calculate estimated reading time
     */
    calculateReadingTime(wordCount) {
        const minutes = Math.ceil(wordCount / this.WORDS_PER_MINUTE);
        return minutes;
    }

    /**
     * Get reading time as formatted string
     */
    getReadingTimeString(minutes) {
        if (minutes < 1) {
            return 'Less than 1 minute';
        } else if (minutes === 1) {
            return '1 minute';
        } else {
            return `${minutes} minutes`;
        }
    }

    /**
     * Check if reader mode is currently active
     */
    isActive() {
        return this.isReaderModeActive;
    }

    /**
     * Store original content before applying reader mode
     */
    storeOriginalContent() {
        this.originalContent = document.documentElement.innerHTML;
    }

    /**
     * Restore original content
     */
    restoreOriginalContent() {
        if (this.originalContent) {
            document.documentElement.innerHTML = this.originalContent;
            this.isReaderModeActive = false;
        }
    }
}

// Export for use in Python
if (typeof window !== 'undefined') {
    window.SeoltoirReaderMode = SeoltoirReaderMode;
}