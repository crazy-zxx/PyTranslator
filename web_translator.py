import time
from typing import Dict, Any

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class WebTranslator:
    def __init__(self, url, input_csspath, output_csspath, clear_csspath, trans_result_wait=1,
                 driver_path='./browser_driver/msedgedriver.exe', is_headless=True,
                 proxy_config: Dict[str, Any] = None):
        """初始化翻译器

        Args:
            driver_path: 浏览器驱动路径
            is_headless: 是否使用无头模式
        """
        self.driver = None
        self.driver_path = driver_path
        self.url = url
        self.input_csspath = input_csspath
        self.output_csspath = output_csspath
        self.clear_csspath = clear_csspath
        self.trans_result_wait = trans_result_wait

        options = webdriver.EdgeOptions()
        if is_headless:
            options.add_argument('--headless')  # 不显示浏览器
        options.add_argument("--disable-gpu")  # 禁用GPU加速
        options.add_argument("--disable-dev-shm-usage")  # 禁用共享内存

        # 配置代理
        if proxy_config and proxy_config.get('using'):
            proxy_str = f"{proxy_config['protocol']}://{proxy_config['address']}:{proxy_config['port']}"
            options.add_argument(f"--proxy-server={proxy_str}")
            if proxy_config.get('username') and proxy_config.get('password'):
                options.add_argument(f"--proxy-auth={proxy_config['username']}:{proxy_config['password']}")

        service = Service(self.driver_path)
        self.driver = webdriver.Edge(service=service, options=options)

        # 设置自定义请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        # 添加请求拦截器
        self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': headers})
        print("浏览器初始化成功")

    def translate(self, text, web_timeout=5):
        """执行翻译

        Args:
            text: 要翻译的文本
            web_timeout: 等待网页加载的最大时间（秒）

        Returns:
            翻译结果字符串或None
        """

        if not self.driver:
            print("错误: 浏览器未初始化")
            return None

        try:
            # 刷新页面
            self.driver.get(self.url)

            # 等待页面状态变为"complete"
            WebDriverWait(self.driver, web_timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            # 定位输入框
            input_element = WebDriverWait(self.driver, web_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.input_csspath))
            )

            # 聚焦元素
            self.driver.execute_script("arguments[0].focus();", input_element)

            # 输入文本
            actions = ActionChains(self.driver)
            actions.send_keys(text).perform()

            # 等待翻译结果
            output_element = WebDriverWait(self.driver, web_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.output_csspath))
            )
            time.sleep(self.trans_result_wait + len(text) // 50)
            result_text = output_element.text

            # 定位清除输入按钮
            clear_element = WebDriverWait(self.driver, web_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.clear_csspath))
            )
            self.driver.execute_script("arguments[0].click();", clear_element)

            return result_text

        except Exception as e:
            print(f"翻译失败: {str(e)}")
            raise

    def quit(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            print("浏览器已关闭")


class BaiduTranslator(WebTranslator):
    def __init__(self, driver_path, is_headless=False, proxy_config: Dict[str, Any] = None):
        print('baidu translator')
        # 配置参数
        url = "https://fanyi.baidu.com/mtpe-individual/multimodal"
        input_csspath = '#editor-text > div.fAuuTI2d > div > div.Ssl84aLh > div > div > div > div > span > span > span'
        output_csspath = '#trans-selection > div > span'
        clear_csspath = '#editor-text > div.fAuuTI2d > div > div.Ssl84aLh > span'
        trans_result_wait = 0.2
        super().__init__(url, input_csspath, output_csspath, clear_csspath, trans_result_wait, driver_path, is_headless,
                         proxy_config)


class YoudaoTranslator(WebTranslator):
    def __init__(self, driver_path, is_headless=False, proxy_config: Dict[str, Any] = None):
        print('youdao translator')
        # 配置参数
        url = "https://fanyi.youdao.com/#/TextTranslate"
        input_csspath = '#js_fanyi_input'
        output_csspath = '#js_fanyi_output_resultOutput > p > span'
        clear_csspath = '#TextTranslate > div.source > div.text-translate-top-right > a'
        trans_result_wait = 0.5
        super().__init__(url, input_csspath, output_csspath, clear_csspath, trans_result_wait, driver_path, is_headless,
                         proxy_config)


class TencentTranSmartTranslator(WebTranslator):
    def __init__(self, driver_path, is_headless=False, proxy_config: Dict[str, Any] = None):
        print('tencent-transmart translator')
        # 配置参数
        url = "https://transmart.qq.com/zh-CN/index"
        input_csspath = '#ORIGINAL_TEXTAREA'
        output_csspath = '#root > div > div.src-routes--container__2sG4U > div > div:nth-child(1) > div:nth-child(2) > div.src-views-InteractiveTranslation-components-PanelTarget--container-content__24R3o > div.src-views-InteractiveTranslation-components-PanelTarget--content__1zYZJ > span.src-views-InteractiveTranslation-components-PanelTarget--content-sentence__viSNx.src-views-InteractiveTranslation-components-PanelTarget--active__1hbv3'
        clear_csspath = '#root > div > div.src-routes--container__2sG4U > div > div:nth-child(1) > div:nth-child(1) > div.src-views-InteractiveTranslation-components-PanelSource--container-textarea__2SIoV'
        trans_result_wait = 0.5
        super().__init__(url, input_csspath, output_csspath, clear_csspath, trans_result_wait, driver_path, is_headless,
                         proxy_config)


class CaiyunTranslator(WebTranslator):
    def __init__(self, driver_path, is_headless=False, proxy_config: Dict[str, Any] = None):
        print('caiyun translator')
        # 配置参数
        url = "https://fanyi.caiyunapp.com/"
        input_csspath = '#textarea'
        output_csspath = '#target_trans_0'
        clear_csspath = '#app > div > div > div.page-content > div.page-content-box > div > div > div.trans-action-box > div > div.two-column-layout > div:nth-child(1) > div > div.column-choose-langBox > img.closeImg'
        trans_result_wait = 0.2
        super().__init__(url, input_csspath, output_csspath, clear_csspath, trans_result_wait, driver_path, is_headless,
                         proxy_config)


class AliTranslator(WebTranslator):
    def __init__(self, driver_path, is_headless=False, proxy_config: Dict[str, Any] = None):
        print('ali translator')
        # 配置参数
        url = "https://translate.alibaba.com/"
        input_csspath = '#source'
        output_csspath = '#pre'
        clear_csspath = '#root > div > div > div.smart-translation > div > div.tabs-content > div > div.example > div.translat-exhibit > div > div.original > div > span'
        trans_result_wait = 0.3
        super().__init__(url, input_csspath, output_csspath, clear_csspath, trans_result_wait, driver_path, is_headless,
                         proxy_config)


class GoogleTranslator(WebTranslator):
    def __init__(self, driver_path, is_headless=False, proxy_config: Dict[str, Any] = None):
        print('google translator')
        # 配置参数
        url = "https://translate.google.com/"
        input_csspath = '#yDmH0d > c-wiz > div > div.ToWKne > c-wiz > div.OlSOob > c-wiz > div.ccvoYb > div.AxqVh > div.OPPzxe > div > c-wiz > span > span > div > textarea'
        output_csspath = '#yDmH0d > c-wiz > div > div.ToWKne > c-wiz > div.OlSOob > c-wiz > div.ccvoYb > div.AxqVh > div.OPPzxe > c-wiz > div > div.usGWQd > div > div.lRu31 > span.HwtZe > span > span'
        clear_csspath = '#yDmH0d > c-wiz > div > div.ToWKne > c-wiz > div.OlSOob > c-wiz > div.ccvoYb > div.AxqVh > div.OPPzxe > div > c-wiz > div.DVHrxd > span > button'
        trans_result_wait = 1
        super().__init__(url, input_csspath, output_csspath, clear_csspath, trans_result_wait, driver_path, is_headless,
                         proxy_config)


class DeepLTranslator(WebTranslator):
    def __init__(self, driver_path, is_headless=False, proxy_config: Dict[str, Any] = None):
        print('deepl translator')
        # 配置参数
        url = "https://www.deepl.com/zh/translator"
        input_csspath = '#textareasContainer > div.rounded-es-inherit.relative.min-h-\[240px\].min-w-0.md\:min-h-\[clamp\(250px\,50vh\,557px\)\].mobile\:min-h-0.TextTranslatorLayout-module--textareaContainerMobilePortraitMaxHeight--50d46 > section > div > div.relative.flex-1.rounded-inherit.mobile\:min-h-0 > d-textarea > div:nth-child(1)'
        output_csspath = '#textareasContainer > div.rounded-ee-inherit.relative.min-h-\[240px\].min-w-0.md\:min-h-\[clamp\(250px\,50vh\,557px\)\].mobile\:min-h-0.mobile\:flex-1.max-\[768px\]\:min-h-\[375px\].TextTranslatorLayout-module--textareaContainerMobilePortraitMaxHeight--50d46 > section > div.relative.flex.flex-1.flex-col.rounded-inherit.mobile\:min-h-0 > d-textarea > div > p > span'
        clear_csspath = '#translator-source-clear-button'
        trans_result_wait = 2
        super().__init__(url, input_csspath, output_csspath, clear_csspath, trans_result_wait, driver_path, is_headless,
                         proxy_config)


# 使用示例
if __name__ == "__main__":
    # 配置参数
    driver_path = './browser_driver/msedgedriver.exe'
    is_headless = False
    proxy_config = {
        "using": True,
        "protocol": "http",
        "address": "127.0.0.1",
        "port": 7890,
        "username": "",
        "password": "",
    }

    # 定义翻译器配置
    translator_classes = [
        BaiduTranslator,
        YoudaoTranslator,
        CaiyunTranslator,
        AliTranslator,
        TencentTranSmartTranslator,
        GoogleTranslator,
        DeepLTranslator
    ]

    # 轮流测试翻译器
    for translator_class in translator_classes:
        print(f"\n=== 测试 {translator_class.__name__} ===")

        # 初始化单个翻译器
        translator = translator_class(driver_path, is_headless=is_headless, proxy_config=proxy_config)

        try:
            # 执行翻译
            result = translator.translate("Hello, world!")
            print(f"翻译结果: {result}")

            # 翻译另一个文本
            result = translator.translate("Python自动化测试")
            print(f"翻译结果: {result}")

        except Exception as e:
            print(f"测试 {translator_class.__name__} 时出错: {str(e)}")

        finally:
            # 关闭浏览器
            translator.quit()
            print(f"{translator_class.__name__} 测试完成并已关闭")
