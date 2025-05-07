"""
Custom Selenium middleware that fixes the 'remote.options' import issue
"""
from importlib import import_module

from scrapy import signals
from scrapy.exceptions import NotConfigured
from scrapy.http import HtmlResponse
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium import webdriver


class SeleniumMiddleware:
    """Scrapy middleware handling the requests using Selenium"""

    def __init__(self, driver_name, driver_executable_path,
                 driver_arguments, browser_executable_path,
                 command_executor):
        """Initialize the selenium webdriver

        Parameters
        ----------
        driver_name: str
            The selenium ``WebDriver`` to use
        driver_executable_path: str
            The path of the executable binary of the driver
        driver_arguments: list
            A list of arguments to initialize the driver
        browser_executable_path: str
            The path of the executable binary of the browser
        command_executor: str
            URL of remote server (if using remote webdriver)
        """
        self.driver_name = driver_name
        self.driver_executable_path = driver_executable_path
        self.browser_executable_path = browser_executable_path
        self.driver_arguments = driver_arguments
        self.command_executor = command_executor
        
        # We'll initialize the driver in process_request instead
        # so we can add proxy settings per request
        self.driver = None

    def _create_driver(self, proxy=None):
        """Create a WebDriver instance with optional proxy settings"""
        webdriver_base_path = f'selenium.webdriver.{self.driver_name}'

        # Import driver options class
        if self.driver_name == 'remote':
            # For remote, we'll use Chrome options since most remote drivers are Chrome
            driver_options = ChromeOptions()
        else:
            try:
                driver_options_module = import_module(f'{webdriver_base_path}.options')
                driver_options_class = getattr(driver_options_module, 'Options')
                driver_options = driver_options_class()
            except (ImportError, AttributeError):
                # Some drivers like Chrome and Firefox have different option structures
                if self.driver_name == 'chrome':
                    driver_options = ChromeOptions()
                elif self.driver_name == 'firefox':
                    driver_options = FirefoxOptions()
                else:
                    raise NotConfigured(f'Unknown driver: {self.driver_name}')

        # Set arguments for the driver
        if self.driver_arguments:
            for argument in self.driver_arguments:
                driver_options.add_argument(argument)

        # Add proxy if specified
        if proxy:
            driver_options.add_argument(f'--proxy-server={proxy}')

        # Set browser executable path
        if self.browser_executable_path:
            driver_options.binary_location = self.browser_executable_path

        # Initialize the driver
        if self.driver_name == 'remote':
            driver = webdriver.Remote(
                command_executor=self.command_executor,
                options=driver_options
            )
        else:
            driver_class = getattr(webdriver, self.driver_name.capitalize())
            driver_kwargs = {
                'executable_path': self.driver_executable_path,
                'options': driver_options,
            }
            if self.driver_name == 'firefox':
                from selenium.webdriver.firefox.service import Service
                driver_kwargs['service'] = Service(self.driver_executable_path)
                driver_kwargs.pop('executable_path')
            elif self.driver_name == 'chrome':
                from selenium.webdriver.chrome.service import Service
                driver_kwargs['service'] = Service(self.driver_executable_path)
                driver_kwargs.pop('executable_path')
            
            driver = driver_class(**driver_kwargs)
            
        return driver

    @classmethod
    def from_crawler(cls, crawler):
        """Initialize the middleware with the crawler settings"""
        driver_name = crawler.settings.get('SELENIUM_DRIVER_NAME')
        driver_executable_path = crawler.settings.get('SELENIUM_DRIVER_EXECUTABLE_PATH')
        browser_executable_path = crawler.settings.get('SELENIUM_BROWSER_EXECUTABLE_PATH')
        driver_arguments = crawler.settings.get('SELENIUM_DRIVER_ARGUMENTS')
        command_executor = crawler.settings.get('SELENIUM_COMMAND_EXECUTOR')

        if not driver_name:
            raise NotConfigured('SELENIUM_DRIVER_NAME must be set')

        middleware = cls(
            driver_name=driver_name,
            driver_executable_path=driver_executable_path,
            driver_arguments=driver_arguments,
            browser_executable_path=browser_executable_path,
            command_executor=command_executor
        )

        crawler.signals.connect(middleware.spider_closed, signals.spider_closed)

        return middleware

    def process_request(self, request, spider):
        """Process a request using the selenium driver if applicable"""
        if not request.meta.get('selenium'):
            return None

        # Get proxy from meta if available
        proxy = request.meta.get('selenium_proxy')
        if proxy:
            spider.logger.info(f"Using Selenium proxy: {proxy}")
            
        # Close existing driver if it exists
        if self.driver:
            self.driver.quit()
            
        # Create a new driver with optional proxy
        self.driver = self._create_driver(proxy)
        
        # Get the page
        self.driver.get(request.url)

        # Wait for JavaScript to execute if needed
        if request.meta.get('wait_time'):
            self.driver.implicitly_wait(request.meta.get('wait_time'))

        body = str.encode(self.driver.page_source)

        # Don't quit the driver here, we'll reuse it for subsequent requests
        # within the same spider job with the same proxy settings

        # Expose the driver to the response
        return HtmlResponse(
            self.driver.current_url,
            body=body,
            encoding='utf-8',
            request=request
        )

    def spider_closed(self, spider):
        """Shutdown the driver when spider is closed"""
        if self.driver:
            self.driver.quit()