import { Agent, request } from 'node:http';
import { isHostOrigin } from './policy.js';

/** Exchange the private startup secret over a direct, bounded loopback connection. */
export async function authenticateHost(origin: string, bootstrapToken: string): Promise<string> {
  if (!isHostOrigin(origin)) throw new Error('Invalid Host origin.');
  const agent = new Agent({ keepAlive: false, proxyEnv: {} });
  try {
    return await new Promise<string>((resolve, reject) => {
      const connection = request(`${origin}/internal/bootstrap`, {
        method: 'POST', agent, signal: AbortSignal.timeout(5000),
        headers: { authorization: `Bearer ${bootstrapToken}` },
      }, response => {
        if (response.statusCode !== 200) {
          response.destroy();
          reject(new Error('Host authentication failed.'));
          return;
        }
        let body = '';
        response.setEncoding('utf8');
        response.on('data', (chunk: string) => {
          body += chunk;
          if (body.length > 1024) response.destroy(new Error('Invalid Host authentication.'));
        });
        response.on('error', reject);
        response.on('end', () => {
          try {
            const receipt: unknown = JSON.parse(body);
            if (typeof receipt !== 'object' || receipt === null || !('sessionToken' in receipt)
              || typeof receipt.sessionToken !== 'string' || !/^[a-f0-9]{64}$/.test(receipt.sessionToken)) {
              throw new Error('Invalid Host authentication.');
            }
            resolve(receipt.sessionToken);
          } catch { reject(new Error('Invalid Host authentication.')); }
        });
      });
      connection.on('error', reject);
      connection.end();
    });
  } finally { agent.destroy(); }
}
