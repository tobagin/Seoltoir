/**
 * Simplified Reader Mode for Testing
 */

function simpleReaderMode() {
    console.log('[READER_MODE] Simple reader mode starting');
    
    try {
        // Find main content
        const article = document.querySelector('article') || 
                       document.querySelector('main') || 
                       document.querySelector('.content') ||
                       document.querySelector('.post');
        
        if (!article) {
            console.log('[READER_MODE] No article element found');
            return { success: false, error: 'No article content found' };
        }
        
        console.log('[READER_MODE] Article found:', article.tagName);
        
        // Get article content
        const title = document.querySelector('h1')?.textContent || document.title || 'Article';
        const content = article.innerHTML;
        const wordCount = (article.textContent || '').split(/\s+/).length;
        const readingTime = Math.ceil(wordCount / 200);
        
        console.log('[READER_MODE] Article extracted:', { title, wordCount, readingTime });
        
        return {
            success: true,
            article: {
                title: title,
                content: content,
                wordCount: wordCount,
                readingTime: readingTime,
                author: null,
                publishDate: null
            }
        };
    } catch (error) {
        console.error('[READER_MODE] Simple reader mode error:', error);
        return { success: false, error: error.message };
    }
}

// Execute and return result
simpleReaderMode();