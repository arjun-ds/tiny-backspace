
// Main server functionality
import modal from 'modal-client';
import { FastAPI } from 'fastapi';
import { CORSMiddleware } from 'fastapi.middleware.cors';
import { StaticFiles } from 'fastapi.staticfiles';
import { BaseModel } from 'pydantic';
import { HttpUrl } from 'pydantic';
import { json } from 'fastapi.responses';

// Create app instance
const app = modal.App('backspace-agent');
const webApp = new FastAPI({
  title: 'Backspace Coding Agent'
});

// Add CORS middleware
webApp.add_middleware(CORSMiddleware, {
  allow_origins: ['*'],
  allow_credentials: true,
  allow_methods: ['*'], 
  allow_headers: ['*']
});

// Health check endpoint
webApp.get('/healthz', async () => {
  return {
    status: 'ok',
    service: 'Backspace Coding Agent'
  };
});

// Request model
class CodeRequest extends BaseModel {
  repoUrl: HttpUrl;
  prompt: string;
}

// Main code endpoint
webApp.post('/code', async (request) => {
  const { repoUrl, prompt } = request;
  
  // Run agent and format output
  const events = await runAgent(repoUrl, prompt);
  return new StreamingResponse(events, {
    media_type: 'text/event-stream',
    headers: {
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no'
    }
  });
});

// Mount static files
const staticDir = '/root/web/out';
if (fs.existsSync(staticDir)) {
  webApp.mount('/', StaticFiles({
    directory: staticDir,
    html: true
  }));
  console.log(`Static files mounted from ${staticDir}`);
} else {
  console.log(`Warning: Static directory ${staticDir} not found`);
}

// Export app
export default webApp;
