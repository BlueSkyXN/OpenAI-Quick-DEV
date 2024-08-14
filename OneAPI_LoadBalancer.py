import time
import random
import asyncio
import aiohttp
import logging
from collections import deque
import tiktoken

# 设置日志配置，将日志等级设置为 DEBUG 以记录详细信息
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class LoadBalancer:
    def __init__(self, targets, algorithm='weighted_random', concurrency_limit=10):
        """
        初始化负载均衡器
        :param targets: 目标服务器列表，每个目标是一个包含各种配置的字典
        :param algorithm: 负载均衡算法，可选 'round_robin'（轮询）, 'random'（随机）, 
                          'weighted_random'（加权随机）, 'least_used'（最少使用）, 
                          'dynamic_least_load'（动态最低负载）, 'lowest_latency'（最低延迟）
        :param concurrency_limit: 并发请求数限制，默认值为10
        """
        # 缺省值设置：为每个目标设置默认的流控和重试配置
        default_config = {
            'id': None,  # 目标的唯一标识符
            'sk': 'sk-test',  # 默认的API密钥
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',  # 默认的User-Agent
            'weight': 1,  # 默认的权重
            'api_url': None,  # 默认的API URL（如果设置，将优先于api_domain）
            'api_domain': 'https://api.oneapi.com',  # 默认的API域名
            'model': 'gpt-4o-mini',  # 默认的模型名称，用于请求体中
            'rps_limit': 2,  # 每秒请求数限制
            'rpm_limit': 120,  # 每分钟请求数限制
            'tpm_limit': 1000000,  # 每分钟内容令牌数限制
            'mrr': 0.3,  # 最短请求间隔
            'sri': 0.5,  # 成功到请求的间隔
            '429_wait_time': 60,  # 触发429错误后的等待时间
            '500_wait_time': 5,  # 触发500错误后的等待时间
            '502_wait_time': 5,  # 触发502错误后的等待时间
            '503_wait_time': 5,  # 触发503错误后的等待时间
            '403_wait_time': 15,  # 触发403错误后的等待时间
            'retry_wait_time': 3,  # 单请求任务重试等待时间
            'max_retries': 2  # 单请求任务重试次数
        }

        # 将缺省值应用到每个目标配置中
        self.targets = [{**default_config, **target} for target in targets]
        self.algorithm = algorithm
        self.last_used = {target['id']: 0 for target in self.targets}  # 记录每个目标最后一次使用时间
        self.request_counts = {target['id']: deque(maxlen=100) for target in self.targets}  # 记录每个目标的请求时间戳
        self.token_counts = {target['id']: deque(maxlen=100) for target in self.targets}  # 记录每个目标的令牌使用情况
        self.last_request_times = {target['id']: deque(maxlen=100) for target in self.targets}  # 初始化 last_request_times
        self.lock = asyncio.Lock()  # 用于并发处理的异步锁
        self.concurrency_limit = concurrency_limit  # 并发请求数限制
        self.semaphore = asyncio.Semaphore(concurrency_limit)  # 异步信号量，用于限制并发数
        self.current_index = 0  # 初始化轮询算法的索引

        # 统一使用 gpt-4-32k 的编码器
        self.encoder = tiktoken.get_encoding('cl100k_base')

    async def _round_robin(self):
        """
        轮询算法实现
        :return: 轮询选中的目标服务器
        """
        target = self.targets[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.targets)
        return target

    async def _weighted_random(self):
        """
        加权随机算法实现
        :return: 根据权重随机选中的目标服务器
        """
        total_weight = sum(target.get('weight', 1) for target in self.targets)
        r = random.uniform(0, total_weight)
        for target in self.targets:
            r -= target.get('weight', 1)
            if r <= 0:
                return target

    async def _least_used(self):
        """
        最少使用算法实现
        :return: 最近最少使用的目标服务器
        """
        return min(self.targets, key=lambda x: self.last_used[x['id']])

    async def _dynamic_least_load(self):
        """
        动态最低负载算法实现
        :return: 负载最小的目标服务器
        """
        current_time = time.time()
        loads = []
        for target in self.targets:
            window = target.get('load_window', 60)  # 默认1分钟窗口
            # 计算窗口期内的请求数
            requests_in_window = sum(1 for t in self.last_request_times[target['id']]
                                    if current_time - t <= window)
            
            # 计算 RPS 限制 * 60 和 RPM 限制的较小值
            rps_limit = target.get('rps_limit', float('inf')) * 60
            rpm_limit = target.get('rpm_limit', float('inf'))
            effective_limit = min(rps_limit, rpm_limit)
            
            # 计算负载比例，防止除以0的情况
            if effective_limit == 0:
                load = float('inf')  # 如果限制为0，负载为无穷大，避免选择这个目标
            else:
                load = requests_in_window / effective_limit
            
            loads.append((target, load))
        
        # 返回负载最小的目标服务器
        return min(loads, key=lambda x: x[1])[0]

    async def _lowest_latency(self):
        """
        最低延迟算法实现
        :return: 延迟最小的目标服务器
        """
        latencies = [await self._get_latency(target) for target in self.targets]
        return min(latencies, key=lambda x: x[1])[0]

    async def _get_latency(self, target):
        """
        获取目标服务器的延迟
        :param target: 目标服务器字典
        :return: 目标服务器和延迟值的元组
        """
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(target.get('latency_check_url', target['api_domain'])):
                    return target, time.time() - start_time
        except:
            return target, float('inf')

    async def _check_target_availability(self, target):
        """
        检查目标服务器是否可用，基于流控策略
        :param target: 目标服务器字典
        :return: 如果可用返回True，否则返回False
        """
        current_time = time.time()
        target_id = target['id']

        # 检查每秒请求数限制（RPS）
        if target.get('rps_limit'):
            if len(self.last_request_times[target_id]) > 0 and current_time - self.last_request_times[target_id][-1] < 1 / target['rps_limit']:
                logging.warning(f"Target {target_id} is unavailable due to RPS limit.")
                return False

        # 检查每分钟请求数限制（RPM）
        if target.get('rpm_limit'):
            requests_in_last_minute = sum(1 for t in self.last_request_times[target_id]
                                        if current_time - t <= 60)
            if requests_in_last_minute >= target['rpm_limit']:
                logging.warning(f"Target {target_id} is unavailable due to RPM limit.")
                return False

        # 检查每分钟令牌数限制（TPM）
        if target.get('tpm_limit'):
            # 计算过去一分钟的令牌数总和
            token_count_in_last_minute = sum(tokens for tokens, timestamp in self.token_counts[target_id]
                                            if current_time - timestamp <= 60)
            if token_count_in_last_minute >= target['tpm_limit']:
                logging.warning(f"Target {target_id} is unavailable due to TPM limit.")
                return False

        # 检查最短请求间隔（MRR）
        if target.get('mrr'):
            if len(self.last_request_times[target_id]) > 0 and current_time - self.last_request_times[target_id][-1] < target['mrr']:
                logging.warning(f"Target {target_id} is unavailable due to MRR limit.")
                return False

        # 检查成功到请求的间隔（SRI）
        if target.get('sri'):
            if self.last_used[target_id] and current_time - self.last_used[target_id] < target['sri']:
                logging.warning(f"Target {target_id} is unavailable due to SRI limit.")
                return False

        # 检查各种错误的等待时间
        for error_code in [429, 500, 502, 503, 403]:
            if target.get(f'{error_code}_wait_time'):
                last_error_time = getattr(self, f'last_{error_code}_time', {}).get(target_id, 0)
                if last_error_time + target[f'{error_code}_wait_time'] > current_time:
                    logging.warning(f"Target {target_id} is unavailable due to {error_code} wait time.")
                    return False

        return True

    async def get_target(self):
        """
        获取当前可用的目标服务器
        :return: 选中的目标服务器字典
        """
        async with self.lock:
            for attempt in range(3):  # 尝试次数
                # 根据选择的算法获取目标
                if self.algorithm == 'round_robin':
                    target = await self._round_robin()
                elif self.algorithm == 'random':
                    target = random.choice(self.targets)
                elif self.algorithm == 'weighted_random':
                    target = await self._weighted_random()
                elif self.algorithm == 'least_used':
                    target = await self._least_used()
                elif self.algorithm == 'dynamic_least_load':
                    target = await self._dynamic_least_load()
                elif self.algorithm == 'lowest_latency':
                    target = await self._lowest_latency()
                else:
                    raise ValueError("Invalid algorithm")

                if await self._check_target_availability(target):
                    logging.info(f"Selected target: {target['id']} with API Domain: {target['api_domain']}")
                    return target
                else:
                    logging.warning(f"Target {target['id']} is currently unavailable. Retrying... ({attempt + 1}/3)")
                    await asyncio.sleep(0.1)  # 如果目标不可用，等待一段时间后再重试

            logging.error("All targets are currently unavailable after multiple attempts.")
            return None


    async def report_success(self, target, token_count):
        """
        报告请求成功，更新相关状态
        :param target: 目标服务器字典
        :param token_count: 本次请求使用的令牌数
        """
        target_id = target['id']
        self.last_used[target_id] = time.time()  # 更新最后使用时间
        self.request_counts[target_id].append(time.time())  # 记录请求时间
        self.token_counts[target_id].append((token_count, time.time()))  # 记录令牌数和时间戳
        self.last_request_times[target_id].append(time.time())  # 记录请求时间戳
        logging.info(f"Request to {target_id} succeeded with {token_count} tokens used.")

    async def report_failure(self, target, status_code):
        """
        报告请求失败，记录错误码及时间
        :param target: 目标服务器字典
        :param status_code: 请求失败时的HTTP状态码
        """
        target_id = target['id']
        current_time = time.time()
        if status_code in [429, 500, 502, 503, 403]:
            # 根据错误码记录最后触发时间
            setattr(self, f'last_{status_code}_time', {**getattr(self, f'last_{status_code}_time', {}), target_id: current_time})
        logging.error(f"Request to {target_id} failed with status code {status_code}.")

    async def send_request(self, target, request_data):
        headers = {
            'Authorization': f"Bearer {target['sk']}",
            'User-Agent': target.get('user_agent', 'LoadBalancer/1.0'),
            'Content-Type': 'application/json'
        }

        # 检查 api_url，如果为 None 字符串或者不是以 'http' 开头，则使用 api_domain 加上默认路径
        if not target['api_url'] or not target['api_url'].startswith('http'):
            url = f"{target['api_domain']}/v1/chat/completions"
        else:
            url = target['api_url']

        logging.debug(f"Constructed URL for request: {url}")

        # 在请求数据中填入 model 字段
        request_data['model'] = target['model']

        # 计算请求数据的令牌数
        token_count = len(self.encoder.encode(str(request_data)))

        async with self.semaphore:  # 使用信号量控制并发
            async with aiohttp.ClientSession() as session:
                for attempt in range(target.get('max_retries', 3)):  # 根据最大重试次数进行重试
                    try:
                        logging.debug(f"Sending request to {url} with data: {request_data}")
                        async with session.post(url, json=request_data, headers=headers) as response:
                            response_data = await response.text()
                            if response.status == 200:  # 请求成功
                                await self.report_success(target, token_count)
                                logging.debug(f"Received response from {url}: {response_data}")
                                return await response.json()
                            else:
                                await self.report_failure(target, response.status)  # 记录失败
                                logging.debug(f"Received error response from {url}: {response_data}")
                                if response.status not in [429, 500, 502, 503, 403]:
                                    return None
                    except aiohttp.ClientError as e:
                        await self.report_failure(target, 0)  # 客户端错误，记录为0
                        logging.error(f"ClientError during request to {url}: {str(e)}")

                    await asyncio.sleep(target.get('retry_wait_time', 1))  # 重试前等待

        return None


    async def process_request(self, request_data):
        """
        处理请求，选择目标并发送请求
        :param request_data: 请求的数据
        :return: 目标服务器的响应
        """
        total_wait_time = 0  # 初始化总等待时间
        max_wait_time = 300  # 最大等待时间300秒
        wait_interval = 1  # 每次重试间隔1秒

        while total_wait_time < max_wait_time:
            target = await self.get_target()  # 获取目标服务器

            if target is not None:
                if target.get('tpm_limit'):
                    token_count = len(self.encoder.encode(str(request_data)))  # 计算请求的数据令牌数
                    if sum(tokens for tokens, timestamp in self.token_counts[target['id']]
                        if time.time() - timestamp <= 60) + token_count > target['tpm_limit']:
                        logging.warning(f"TPM limit exceeded for target {target['id']}. Request not sent.")
                        return None  # 如果令牌数超出限制，返回None

                return await self.send_request(target, request_data)  # 发送请求并返回响应

            # 如果未找到可用目标，等待1秒后重试
            await asyncio.sleep(wait_interval)
            total_wait_time += wait_interval
            logging.warning(f"No available target found. Retrying in {wait_interval} seconds...")

        # 超过300秒未找到可用目标
        logging.error(f"Failed to obtain a valid target after {total_wait_time} seconds. Aborting request.")
        return None



# 使用示例：执行并发测试
async def main():
    targets = [
        {
            'id': '1',
            'model': 'hunyuan-lite',
            'weight': 1,
            'rps_limit': 10
        },
        {
            'id': '2',
            'model': 'SparkDesk',
            'weight': 1,
            'rps_limit': 4
        }
        # 添加更多的模型配置
    ]

    lb = LoadBalancer(targets, algorithm='weighted_random')

    # 创建20个任务，每个任务请求不同的数字
    tasks = []
    semaphore = asyncio.Semaphore(10)  # 并发限制为10

    async def execute_request(request_data):
        async with semaphore:
            return await lb.process_request(request_data)

    for i in range(1, 21):
        request_data = {
            "messages": [{"role": "user", "content": f"Please respond with the number {i}"}]
        }
        tasks.append(execute_request(request_data))

    # 等待所有任务完成
    results = await asyncio.gather(*tasks)

    # 打印每个响应的内容
    for index, response in enumerate(results, start=1):
        logging.info(f"Response {index}: {response}")

if __name__ == "__main__":
    asyncio.run(main())
