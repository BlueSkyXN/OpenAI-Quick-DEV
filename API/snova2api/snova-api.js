const TARGET_URL = 'https://fast-api.snova.ai/v1/chat/completions';
const MODEL_OVERRIDE = ''; // Set this to override the model

// More： https://www.blueskyxn.com/202408/7089.html
// 和 https://github.com/BlueSkyXN/OpenAI-Quick-DEV/blob/main/API/snova2api/snova2api.js 的逆向API的区别有且仅有目标URL不同
// 有人发的 https://github.com/GrayXu/sambanova-api-ai-proxy/blob/main/cf-worker.js 实际上连oneapi都无法过测，我不知道为什么好意思发出来，问题和 https://github.com/lingo34/sambanova-ai-proxy/blob/main/cf-worker.js 基本半斤八两

export default {
  async fetch(request) {
    if (request.method === 'POST' && request.url.endsWith('/v1/chat/completions')) {
      try {
        const originalPayload = await request.json();
        const isStreamMode = originalPayload.stream === true; // 检查用户是否指定了流模式

        // Override the model if MODEL_OVERRIDE is set
        if (MODEL_OVERRIDE && MODEL_OVERRIDE.trim() !== '') {
          originalPayload.model = MODEL_OVERRIDE;
        }

        // 强制添加 "stream": true 到目标API请求中，因为目标API只支持流模式
        originalPayload.stream = true;

        const modifiedPayload = {
          body: {
            ...originalPayload,
            stop: ["<|eot_id|>"]
          },
          env_type: "tp16405b"
        };

        const options = {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(modifiedPayload)
        };

        // 发送请求到目标API
        const response = await fetch(TARGET_URL, options);

        // 如果用户请求了流模式
        if (isStreamMode) {
          // 直接将流数据逐步传输给客户端
          const streamResponse = new ReadableStream({
            async start(controller) {
              const reader = response.body.getReader();
              const decoder = new TextDecoder();

              while (true) {
                const { done, value } = await reader.read();
                if (done) {
                  controller.close();
                  break;
                }
                // 将流数据发送给客户端
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                for (const line of lines) {
                  if (line.startsWith('data:')) {
                    const data = line.replace(/^data: /, '').trim();
                    if (data) {
                      controller.enqueue(new TextEncoder().encode(`data: ${data}\n\n`));
                    }
                  }
                }
              }
            }
          });

          return new Response(streamResponse, {
            status: 200,
            headers: {
              'Content-Type': 'text/event-stream',
              'Cache-Control': 'no-cache',
              'Access-Control-Allow-Origin': '*',
              'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
              'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            }
          });

        } else {
          // 非流模式：拼接流数据，并一次性返回完整响应
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let completeResponse = '';
          let isDone = false;
          let finishReason = null;
          let statistics = {};

          while (!isDone) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
              if (line.startsWith('data:')) {
                const data = line.replace(/^data: /, '').trim();

                if (data === '[DONE]') {
                  isDone = true;
                  break;
                }

                if (data) {
                  try {
                    const jsonChunk = JSON.parse(data);
                    if (jsonChunk.choices && jsonChunk.choices[0].delta && jsonChunk.choices[0].delta.content) {
                      completeResponse += jsonChunk.choices[0].delta.content;
                    }

                    if (jsonChunk.choices && jsonChunk.choices[0].finish_reason) {
                      finishReason = jsonChunk.choices[0].finish_reason;
                    }

                    if (jsonChunk.usage) {
                      statistics = jsonChunk.usage;
                    }

                  } catch (err) {
                    console.error('Failed to parse JSON chunk:', err);
                  }
                }
              }
            }
          }

          return new Response(JSON.stringify({
            id: "complete-id",
            object: "chat.completion",
            created: Date.now(),
            model: originalPayload.model || "default-model",
            choices: [{
              index: 0,
              message: {
                role: "assistant",
                content: completeResponse
              },
              finish_reason: finishReason || "stop"
            }],
            usage: statistics
          }), {
            status: 200,
            headers: {
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*',
              'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
              'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            }
          });
        }

      } catch (error) {
        console.error('Error processing request:', error);
        return new Response(JSON.stringify({ error: 'Bad Request' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
      }
    } else {
      return new Response(JSON.stringify({ error: 'Not Found' }), { status: 404, headers: { 'Content-Type': 'application/json' } });
    }
  }
};
