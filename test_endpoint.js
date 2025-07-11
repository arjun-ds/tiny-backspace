const axios = require('axios');

/**
 * Test the /code endpoint with SSE streaming
 * @param {string} baseUrl - Base URL of the deployed Modal app
 * @param {string} repoUrl - GitHub repository URL to test with
 * @param {string} prompt - Coding prompt to send
 * @param {number} timeout - Timeout in seconds for SSE stream
 * @param {boolean} verbose - Print detailed progress messages
 * @returns {Promise<object>} Test results with success status and details
 */
async function testEndpoint(baseUrl, repoUrl = 'https://github.com/psf/requests', prompt = 'Add a docstring to the main function explaining its purpose', timeout = 300, verbose = true) {
    const results = {
        success: false,
        health_check: false,
        sse_connection: false,
        events_received: 0,
        pr_url: null,
        error: null,
        duration: 0
    };

    const startTime = Date.now();

    try {
        // Test health check first
        const healthResponse = await axios.get(`${baseUrl}/healthz`, { timeout: 10000 });
        results.health_check = healthResponse.status === 200;

        if (!results.health_check) {
            results.error = `Health check failed: ${healthResponse.status}`;
            return results;
        }

        // Test main endpoint
        const payload = {
            repoUrl,
            prompt
        };

        const response = await axios({
            method: 'post',
            url: `${baseUrl}/code`,
            data: payload,
            headers: { 'Accept': 'text/event-stream' },
            timeout: timeout * 1000,
            responseType: 'stream'
        });

        if (response.status !== 200) {
            results.error = `HTTP ${response.status}: ${response.statusText}`;
            if (verbose) {
                console.log(`Error: ${response.status}`);
                console.log(`Response: ${response.statusText}`);
            }
            return results;
        }

        results.sse_connection = true;
        
        // Process SSE stream
        const streamStart = Date.now();
        response.data.on('data', chunk => {
            const lines = chunk.toString().split('\n').filter(line => line.trim());
            
            for (const line of lines) {
                if (Date.now() - streamStart > timeout * 1000) {
                    results.error = `Stream timeout after ${timeout}s`;
                    if (verbose) {
                        console.log(`[TIMEOUT] Stream exceeded ${timeout}s`);
                    }
                    return results;
                }

                if (line.startsWith('data: ')) {
                    results.events_received++;
                    try {
                        const data = JSON.parse(line.substring(6));
                        const eventType = data.type || 'unknown';
                        const message = data.message || '';

                        if (eventType === 'error') {
                            results.error = message;
                            if (verbose) {
                                console.log(`data: ${JSON.stringify(data)}`);
                            }
                            return results;
                        } else if (eventType === 'complete') {
                            const prUrl = data.pr_url || '';
                            results.pr_url = prUrl;
                            results.success = true;
                            if (verbose) {
                                console.log(`data: ${JSON.stringify(data)}`);
                            }
                            return results;
                        } else if (verbose) {
                            console.log(`data: ${JSON.stringify(data)}`);
                        }
                    } catch (err) {
                        if (verbose) {
                            console.log(`Invalid JSON: ${line}`);
                        }
                    }
                }
            }
        });

        await new Promise(resolve => response.data.on('end', resolve));

        if (results.events_received === 0) {
            results.error = 'No events received from stream';
        }

        return results;

    } catch (error) {
        if (error.code === 'ECONNABORTED') {
            results.error = `Request timeout after ${timeout}s`;
        } else if (error.code === 'ECONNREFUSED') {
            results.error = 'Could not connect to endpoint';
        } else {
            results.error = error.message;
        }
        if (verbose) {
            console.log(`Error: ${results.error}`);
        }
        return results;
    } finally {
        results.duration = (Date.now() - startTime) / 1000;
    }
}

module.exports = testEndpoint;
