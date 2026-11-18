import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..');

function runPythonBackend(endpoint, bodyData) {
  return new Promise((resolve, reject) => {
    const pythonScript = `
import sys, json
from orbit.api.app import app
from fastapi.testclient import TestClient

client = TestClient(app)
endpoint = sys.argv[1]

if endpoint == '/api/health':
    res = client.get('/api/health')
    print(res.text)
elif endpoint == '/api/demo/run':
    payload = json.loads(sys.argv[2])
    res = client.post('/api/demo/run', json=payload)
    print(res.text)
else:
    res = client.get(endpoint)
    print(res.text)
`;

    const proc = spawn(path.join(PROJECT_ROOT, '.venv/bin/python'), [
      '-c', pythonScript, endpoint, JSON.stringify(bodyData || {})
    ], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONPATH: PROJECT_ROOT }
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', data => stdout += data);
    proc.stderr.on('data', data => stderr += data);

    proc.on('close', code => {
      if (code !== 0) {
        console.error("Python bridge error (code " + code + "):", stderr);
        return reject(new Error(stderr || "Python execution failed"));
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (e) {
        resolve(stdout);
      }
    });
  });
}

export default function orbitApiPlugin() {
  return {
    name: 'vite-plugin-orbit-api',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url.startsWith('/api/')) {
          return next();
        }

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
          try {
            let parsedBody = {};
            if (body) {
              try { parsedBody = JSON.parse(body); } catch (e) {}
            }
            const data = await runPythonBackend(req.url, parsedBody);
            res.setHeader('Content-Type', 'application/json');
            res.statusCode = 200;
            res.end(typeof data === 'string' ? data : JSON.stringify(data));
          } catch (err) {
            console.error("Orbit API Error:", err);
            res.setHeader('Content-Type', 'application/json');
            res.statusCode = 500;
            res.end(JSON.stringify({ error: err.message }));
          }
        });
      });
    }
  };
}
