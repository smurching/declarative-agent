/**
 * Test UI app streaming against LOCAL instance
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const APP_URL = 'http://localhost:3001';  // Local instance

interface StreamEvent {
  type: string;
  [key: string]: any;
}

async function getDatabricksToken(): Promise<string> {
  try {
    const { stdout } = await execAsync(
      'databricks auth token --host https://db-ml-models-dev-us-west.cloud.databricks.com'
    );
    const tokenData = JSON.parse(stdout);
    return tokenData.access_token;
  } catch (error) {
    throw new Error(`Failed to get Databricks token: ${error}`);
  }
}

async function testStreamingChat() {
  console.log('🧪 Testing UI App Streaming (LOCAL)\n');
  console.log('App URL:', APP_URL);
  console.log('Getting auth token...');

  const token = await getDatabricksToken();
  console.log('✓ Got auth token\n');

  const chatId = crypto.randomUUID();

  const requestBody = {
    id: chatId,
    message: {
      id: crypto.randomUUID(),
      role: 'user',
      parts: [
        {
          type: 'text',
          text: 'What is 2+2?',
        },
      ],
    },
    selectedChatModel: 'chat-model',
    selectedVisibilityType: 'private',
  };

  console.log('Request:', JSON.stringify(requestBody, null, 2));
  console.log('\nSending request to /api/chat...\n');

  try {
    const response = await fetch(`${APP_URL}/api/chat`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }

    console.log('✓ Got response, reading stream...\n');
    console.log('='.repeat(60));

    const events: StreamEvent[] = [];
    const textChunks: string[] = [];
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      const lines = text.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);

          if (data === '[DONE]') {
            console.log('\n[Stream End] [DONE]');
            continue;
          }

          try {
            const event: StreamEvent = JSON.parse(data);
            events.push(event);

            console.log(`[Event ${events.length}]`, event.type);

            if (event.type === 'text-delta' && (event.textDelta || event.delta)) {
              const text = event.textDelta || event.delta;
              textChunks.push(text);
              console.log(`  └─ Text: "${text}"`);
            }

            if (event.type === 'error') {
              console.log(`  └─ Error: ${event.errorText}`);
            }
            if (event.type === 'data-error') {
              console.log(`  └─ Data Error: ${event.data}`);
            }
          } catch (e) {
            console.log('[Non-JSON data]', data.substring(0, 100));
          }
        }
      }
    }

    console.log('='.repeat(60));
    console.log('\n📊 RESULTS:\n');
    console.log(`Total events: ${events.length}`);
    console.log(`Text chunks: ${textChunks.length}`);
    console.log(`Combined text: "${textChunks.join('')}"`);
    console.log('\nEvent types:', events.map((e) => e.type).join(', '));

    if (textChunks.length === 0) {
      console.log('\n❌ PROBLEM: No text-delta events received!');
      console.log('\nAll events:');
      events.forEach((e, i) => {
        console.log(`  ${i + 1}. ${JSON.stringify(e)}`);
      });
      throw new Error('No streaming text content - this is the bug!');
    } else {
      console.log('\n✅ SUCCESS: Received streaming text content!');
      console.log(`   Full response: "${textChunks.join('')}"`);
    }
  } catch (error) {
    console.error('\n❌ Error:', error);
    throw error;
  }
}

// Run the test
testStreamingChat()
  .then(() => {
    console.log('\n✅ Test completed successfully!');
    process.exit(0);
  })
  .catch((error) => {
    console.error('\n❌ Test failed:', error.message);
    process.exit(1);
  });
