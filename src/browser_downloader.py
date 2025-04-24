import os
import asyncio
import logging
import time
import re
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class BrowserDownloader:
    """
    Downloader that uses headless browsers to access and download YouTube content.
    This approach is effective when YouTube blocks normal API/yt-dlp requests, as it simulates 
    a real browser. Requires browser automation tools to be installed.
    """
    
    def __init__(self, config):
        self.config = config
        self.download_dir = config.downloads_dir
        self.browser_type = os.getenv('BROWSER_TYPE', 'firefox')  # 'firefox' or 'chrome'
        self.browser_enabled = self._check_browser_availability()
        
        if self.browser_enabled:
            logger.info(f"Browser downloader initialized with {self.browser_type}")
        else:
            logger.warning("Browser downloader is disabled - missing required dependencies")
    
    def _check_browser_availability(self):
        """Check if the required browser automation tools are available"""
        try:
            # Check if playwright is installed
            import importlib.util
            playwright_spec = importlib.util.find_spec("playwright")
            
            if playwright_spec is None:
                return False
                
            # Also verify selenium as a fallback
            selenium_spec = importlib.util.find_spec("selenium")
            
            return playwright_spec is not None or selenium_spec is not None
            
        except ImportError:
            return False
    
    async def download(self, url):
        """Download YouTube video using browser automation"""
        if not self.browser_enabled:
            raise Exception("Browser downloader is not available. Install playwright or selenium to use this method.")
            
        # Extract video ID for better filename handling
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")
        
        # Try different browser automation approaches
        try:
            # Try playwright first (preferred)
            if self._has_playwright():
                return await self._download_with_playwright(url, video_id)
            # Fall back to selenium if playwright is not available
            elif self._has_selenium():
                return await self._download_with_selenium(url, video_id)
            else:
                raise Exception("No browser automation libraries available")
        except Exception as e:
            logger.error(f"Browser download failed: {str(e)}")
            raise Exception(f"Browser download failed: {str(e)}")
    
    def _has_playwright(self):
        """Check if playwright is available"""
        try:
            import playwright
            return True
        except ImportError:
            return False
    
    def _has_selenium(self):
        """Check if selenium is available"""
        try:
            import selenium
            return True
        except ImportError:
            return False
    
    def _extract_video_id(self, url):
        """Extract YouTube video ID from URL"""
        patterns = [
            r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def _download_with_playwright(self, url, video_id):
        """Download YouTube video using Playwright browser automation"""
        # This function will be executed in a separate thread to avoid blocking
        async def _playwright_download():
            from playwright.async_api import async_playwright
            
            logger.info(f"Starting Playwright browser for: {url}")
            async with async_playwright() as p:
                # Determine browser type
                if self.browser_type.lower() == 'firefox':
                    browser_func = p.firefox.launch
                else:
                    browser_func = p.chromium.launch
                
                # Launch browser with download settings
                browser = await browser_func(
                    headless=True,
                    downloads_path=str(self.download_dir)
                )
                
                # Create a new browser context with download settings
                context = await browser.new_context(
                    accept_downloads=True,
                    viewport={'width': 1280, 'height': 720}
                )
                
                # Create a new page
                page = await context.new_page()
                
                # Set a timeout for navigation
                page.set_default_timeout(60000)  # 60 seconds
                
                # Navigate to a YouTube frontend or downloader service
                # Try with a download service first
                try:
                    # Navigate to a download service that works with JavaScript
                    await page.goto(f"https://yout-ube.com/watch?v={video_id}")
                    
                    # Wait for the download button to appear
                    download_button = await page.wait_for_selector('button.download-button, a.download-button', 
                                                                  state='visible', 
                                                                  timeout=30000)
                    
                    # Click the download button
                    await download_button.click()
                    
                    # Wait for the download dialog
                    download = await page.wait_for_download()
                    
                    # Save the file
                    file_path = os.path.join(self.download_dir, f"browser_{video_id}.mp4")
                    await download.save_as(file_path)
                    
                    # Close the browser
                    await browser.close()
                    
                    return file_path
                    
                except Exception as e:
                    logger.warning(f"First download attempt failed: {str(e)}")
                    
                    # Try a different approach - go directly to YouTube and use youtube-dl on the page
                    try:
                        # Navigate to YouTube
                        await page.goto(f"https://www.youtube.com/watch?v={video_id}")
                        
                        # Wait for the video to load
                        await page.wait_for_selector('video', state='visible', timeout=30000)
                        
                        # Get the video title
                        title_element = await page.query_selector('h1.title')
                        title = await title_element.inner_text() if title_element else f"youtube_{video_id}"
                        
                        # Sanitize the title for filename
                        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in ' -_.']).strip()
                        if not safe_title:
                            safe_title = f"youtube_{video_id}"
                        
                        # Create a filename with browser prefix
                        file_path = os.path.join(self.download_dir, f"browser_{safe_title}.mp4")
                        
                        # Extract the video URL using page evaluation
                        video_url = await page.evaluate('''() => {
                            const video = document.querySelector('video');
                            return video ? video.src : null;
                        }''')
                        
                        if not video_url:
                            raise Exception("Could not extract video URL from the page")
                        
                        # Download the video using wget or curl (since we have the direct URL)
                        if os.name == 'posix':  # Linux/Mac
                            download_cmd = f"wget -O '{file_path}' '{video_url}'"
                        else:  # Windows
                            download_cmd = f'curl -o "{file_path}" "{video_url}"'
                        
                        process = await asyncio.create_subprocess_shell(
                            download_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        
                        await process.communicate()
                        
                        # Verify the file exists and has content
                        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                            raise Exception("Downloaded file is empty or does not exist")
                        
                        # Close the browser
                        await browser.close()
                        
                        return file_path
                        
                    except Exception as e:
                        logger.error(f"Second download attempt failed: {str(e)}")
                        await browser.close()
                        raise
        
        # Run the browser download function in a separate thread
        try:
            return await _playwright_download()
        except Exception as e:
            logger.error(f"Playwright download failed: {str(e)}")
            raise Exception(f"Browser automation failed: {str(e)}")
    
    async def _download_with_selenium(self, url, video_id):
        """Download YouTube video using Selenium browser automation"""
        # This function will be executed in a separate thread to avoid blocking
        def _selenium_download():
            from selenium import webdriver
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import time
            
            logger.info(f"Starting Selenium browser for: {url}")
            
            driver = None
            try:
                # Set up browser options
                if self.browser_type.lower() == 'firefox':
                    options = FirefoxOptions()
                    options.headless = True
                    driver = webdriver.Firefox(options=options)
                else:
                    options = ChromeOptions()
                    options.add_argument('--headless')
                    options.add_argument('--disable-gpu')
                    driver = webdriver.Chrome(options=options)
                
                # Navigate to a YouTube downloader service
                driver.get(f"https://yout-ube.com/watch?v={video_id}")
                
                # Wait for the download button
                wait = WebDriverWait(driver, 30)
                download_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.download-button, a.download-button'))
                )
                
                # Get video title
                title_element = driver.find_element(By.CSS_SELECTOR, 'h1.title')
                title = title_element.text if title_element else f"youtube_{video_id}"
                
                # Sanitize the title for filename
                safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in ' -_.']).strip()
                if not safe_title:
                    safe_title = f"youtube_{video_id}"
                
                # Create a filename with browser prefix
                file_path = os.path.join(self.download_dir, f"browser_{safe_title}.mp4")
                
                # Get download URL from the button
                download_url = download_button.get_attribute('href')
                
                if not download_url:
                    # If we can't get the direct URL, we'll need to click and handle browser download
                    # This part is tricky because we need to configure browser download settings
                    raise Exception("Direct download URL not available, interactive download required")
                
                # Download the file using wget or curl
                if os.name == 'posix':  # Linux/Mac
                    download_cmd = f"wget -O '{file_path}' '{download_url}'"
                    os.system(download_cmd)
                else:  # Windows
                    download_cmd = f'curl -o "{file_path}" "{download_url}"'
                    os.system(download_cmd)
                
                # Verify the file exists and has content
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    raise Exception("Downloaded file is empty or does not exist")
                
                return file_path
                
            finally:
                # Close the browser
                if driver:
                    driver.quit()
        
        # Run the selenium download function in a separate thread
        try:
            return await asyncio.to_thread(_selenium_download)
        except Exception as e:
            logger.error(f"Selenium download failed: {str(e)}")
            raise Exception(f"Browser automation failed: {str(e)}") 