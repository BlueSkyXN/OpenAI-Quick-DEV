addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  try {
    // 解析请求体
    const requestData = await request.json()
    const messages = requestData.messages || []

    // 构建要发送到 talkx API 的请求体
    const talkxPayload = {
      roleType: '0',
      productId: 0,
      sessionId: generateUUID(),
      messages: messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    }

    // 向 talkx API 发送请求
    const talkxResponse = await fetch('https://api.talkx.cn/gpt/chat', {
      method: 'POST',
      headers: {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json;charset=utf-8',
        'origin': 'https://web.talkx.cn',
        'referer': 'https://web.talkx.cn/',
        'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'talkx-token': '',
        'user-agent': generateUserAgent(),
      },
      body: JSON.stringify(talkxPayload)
    })

    // 处理 talkx API 的响应
    const contentType = talkxResponse.headers.get('Content-Type') || ''
    let talkxData

    if (contentType.includes('application/json')) {
      talkxData = await talkxResponse.json()
    } else {
      const textResponse = await talkxResponse.text()
      talkxData = {
        choices: [
          {
            message: {
              role: 'assistant',
              content: textResponse
            }
          }
        ]
      }
    }

    // 构建 OpenAI 标准格式的响应
    const openaiResponse = {
      id: generateUUID(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: 'gpt-3.5-turbo',
      choices: talkxData.choices || [],
      usage: {
        prompt_tokens: messages.length,
        completion_tokens: talkxData.choices.length,
        total_tokens: messages.length + talkxData.choices.length
      }
    }

    // 返回响应
    return new Response(JSON.stringify(openaiResponse), {
      headers: { 'Content-Type': 'application/json' }
    })

  } catch (error) {
    return new Response(JSON.stringify({ error: 'Internal Server Error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    })
  }
}

// 生成随机 UUID
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

// 生成随机 User-Agent
function generateUserAgent() {
  const osList = [
    'Windows NT 10.0; Win64; x64',
    'Macintosh; Intel Mac OS X 10_15_7',
    'X11; Linux x86_64'
  ]

  const browserList = [
    `Chrome/${getRandomInt(90, 122)}.${getRandomInt(0, 9)}.${getRandomInt(0, 99)}.${getRandomInt(0, 99)}`,
    `Firefox/${getRandomInt(90, 122)}.${getRandomInt(0, 9)}.${getRandomInt(0, 99)}`,
    `Safari/605.1.15`
  ]

  const os = osList[Math.floor(Math.random() * osList.length)]
  const browser = browserList[Math.floor(Math.random() * browserList.length)]

  return `Mozilla/5.0 (${os}) AppleWebKit/537.36 (KHTML, like Gecko) ${browser} Safari/537.36`
}

// 生成随机整数
function getRandomInt(min, max) {
  min = Math.ceil(min)
  max = Math.floor(max)
  return Math.floor(Math.random() * (max - min + 1)) + min
}
