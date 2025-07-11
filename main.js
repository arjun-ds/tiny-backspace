const express = require('express');
const cors = require('cors');
const { default: fetch } = require('node-fetch');
const path = require('path');

const app = express();

// Add CORS middleware
app.use(cors({
    origin: '*',
    credentials: true,
    methods: ['*'],
    allowedHeaders: ['*']
}));

// Parse JSON bodies
app.use(express.json());

// Health check endpoint
app.get('/healthz', (req, res) => {
    res.json({
        status: 'ok',
        service: 'Backspace Coding Agent'
    });
});

// Code changes endpoint
app.post('/code', async (req, res) => {
    const { repoUrl, prompt } = req.body;

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');

    // Initial messages
    res.write(`data: ${JSON.stringify({type: 'AI Message', message: `Starting agent for repository: ${repoUrl}`})}\n\n`);
    res.write(`data: ${JSON.stringify({type: 'AI Message', message: `Task: ${prompt}`})}\n\n`);

    try {
        const { runAgent } = require('./agent');
        for await (const event of runAgent(repoUrl, prompt)) {
            res.write(event);
        }
    } catch (error) {
        res.write(`data: ${JSON.stringify({type: 'error', message: error.message})}\n\n`);
    } finally {
        res.end();
    }
});

// API code endpoint
app.post('/api/code', async (req, res) => {
    const { repoUrl, prompt } = req.body;
    // Forward to /code endpoint
    req.url = '/code';
    app._router.handle(req, res);
});

// Debug endpoint
app.post('/api/code-debug', async (req, res) => {
    const { repoUrl, prompt } = req.body;

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');

    try {
        res.write(`data: ${JSON.stringify({type: 'AI Message', message: 'Starting debug process...'})}\n\n`);

        const githubToken = process.env.GITHUB_TOKEN;
        const anthropicKey = process.env.ANTHROPIC_API_KEY;

        res.write(`data: ${JSON.stringify({type: 'AI Message', message: `GitHub token present: ${Boolean(githubToken)}`})}\n\n`);
        res.write(`data: ${JSON.stringify({type: 'AI Message', message: `Anthropic API key present: ${Boolean(anthropicKey)}`})}\n\n`);

        if (!githubToken || !anthropicKey) {
            res.write(`data: ${JSON.stringify({type: 'error', message: 'Missing required API keys'})}\n\n`);
            return res.end();
        }

        const { CodingAgent } = require('./agent');
        res.write(`data: ${JSON.stringify({type: 'AI Message', message: 'Agent module loaded successfully'})}\n\n`);

        const agent = new CodingAgent(githubToken);
        res.write(`data: ${JSON.stringify({type: 'AI Message', message: 'Agent initialized successfully'})}\n\n`);

        res.write(`data: ${JSON.stringify({type: 'AI Message', message: `Processing repository: ${repoUrl}`})}\n\n`);
        res.write(`data: ${JSON.stringify({type: 'AI Message', message: `Prompt: ${prompt}`})}\n\n`);

        let eventCount = 0;
        for await (const event of agent.processRepository(repoUrl, prompt)) {
            eventCount++;
            event.debug_event_num = eventCount;
            res.write(`data: ${JSON.stringify(event)}\n\n`);
        }

        res.write(`data: ${JSON.stringify({type: 'AI Message', message: `Total events processed: ${eventCount}`})}\n\n`);

    } catch (error) {
        res.write(`data: ${JSON.stringify({type: 'error', message: `Debug stream error: ${error.message}`, traceback: error.stack})}\n\n`);
    } finally {
        res.end();
    }
});

// Serve static files
const staticDir = path.join(__dirname, 'web/out');
if (require('fs').existsSync(staticDir)) {
    app.use(express.static(staticDir));
    console.log(`Static files mounted from ${staticDir}`);
} else {
    console.log(`Warning: Static directory ${staticDir} not found`);
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
