"""
Custom Selenium middleware that fixes the 'remote.options' import issue
Save this in your project as custom_selenium_middleware.py
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
        webdriver_base_path = f'selenium.webdriver.{driver_name}'

        # Import driver options class
        if driver_name == 'remote':
            # For remote, we'll use Chrome options since most remote drivers are Chrome
            self.driver_options = ChromeOptions()
        else:
            try:
                driver_options_module = import_module(f'{webdriver_base_path}.options')
                driver_options_class = getattr(driver_options_module, 'Options')
                self.driver_options = driver_options_class()
            except (ImportError, AttributeError):
                # Some drivers like Chrome and Firefox have different option structures
                if driver_name == 'chrome':
                    self.driver_options = ChromeOptions()
                elif driver_name == 'firefox':
                    self.driver_options = FirefoxOptions()
                else:
                    raise NotConfigured(f'Unknown driver: {driver_name}')

        # Set arguments for the driver
        if driver_arguments:
            for argument in driver_arguments:
                self.driver_options.add_argument(argument)

        # Set browser executable path
        if browser_executable_path:
            self.driver_options.binary_location = browser_executable_path

        # Initialize the driver
        if driver_name == 'remote':
            capabilities = self.driver_options.to_capabilities()
            self.driver = webdriver.Remote(
                command_executor=command_executor,
                options=self.driver_options
            )
        else:
            driver_class = getattr(webdriver, driver_name.capitalize())
            driver_kwargs = {
                'executable_path': driver_executable_path,
                'options': self.driver_options,
            }
            if driver_name == 'firefox':
                from selenium.webdriver.firefox.service import Service
                driver_kwargs['service'] = Service(driver_executable_path)
                driver_kwargs.pop('executable_path')
            elif driver_name == 'chrome':
                from selenium.webdriver.chrome.service import Service
                driver_kwargs['service'] = Service(driver_executable_path)
                driver_kwargs.pop('executable_path')
            
            self.driver = driver_class(**driver_kwargs)

    @classmethod
    def from_crawler(cls, crawler):
        """Initialize the middleware with the crawler settings"""
        driver_name = crawler.settings.get('SELENIUM_DRIVER_NAME')
        driver_executable_path = crawler.settings.get('SELENIUM_DRIVER_EXECUTABLE_PATH')
        browser_executable_path = crawler.settings.get('SELENIUM_BROWSER_EXECUTABLE_PATH')
        driver_arguments = crawler.settings.get('SELENIUM_DRIVER_ARGUMENTS')
        command_executor = crawler.settings.get('SELENIUM_COMMAND_EXECUTOR')
        driver_capabilities = crawler.settings.get('SELENIUM_DRIVER_CAPABILITIES')

        if not driver_name:
            raise NotConfigured('SELENIUM_DRIVER_NAME must be set')

        # If we're using a remote driver and have specific capabilities
        if driver_name == 'remote' and driver_capabilities:
            webdriver.Remote

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

        self.driver.get(request.url)

        # Wait for JavaScript to execute if needed
        if request.meta.get('wait_time'):
            self.driver.implicitly_wait(request.meta.get('wait_time'))

        body = str.encode(self.driver.page_source)

        # Expose the driver to the response
        return HtmlResponse(
            self.driver.current_url,
            body=body,
            encoding='utf-8',
            request=request
        )

    def spider_closed(self):
        """Shutdown the driver when spider is closed"""
        self.driver.quit()