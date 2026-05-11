import re

def normalize_linkedin_url(url):
    """Unified URL normalization for the entire system."""
    if not url: return ""
    url = url.strip().lower()
    
    # Remove protocol
    url = url.replace("https://", "").replace("http://", "")
    
    # Standardize all subdomains (nl., in., www., etc) to just 'linkedin.com'
    url = re.sub(r'^[a-z]{2}\.linkedin\.com', 'linkedin.com', url)
    url = url.replace("www.linkedin.com", "linkedin.com")
    
    # Remove trailing slash and parameters
    return url.split('?')[0].rstrip('/')
