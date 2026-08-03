/**
 * Shared Hook Utilities
 * Common functions used across multiple Claude Code hooks.
 *
 * Usage:
 *   const { readStdin, shouldSkipFile, allowAndExit, blockAndExit } = require('./hook-utils');
 */

const readline = require('readline');

// File extensions to skip (binary, media, etc.)
const SKIP_EXTENSIONS = [
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
    '.mp3', '.mp4', '.wav', '.avi', '.mov',
    '.pdf', '.zip', '.tar', '.gz',
    '.woff', '.woff2', '.ttf', '.eot',
    '.lock', '.sum'
];

// Base path patterns to skip
const SKIP_PATTERNS_BASE = [
    /node_modules\//i,
    /vendor\//i,
    /\.git\//i,
    /package-lock\.json$/i,
    /composer\.lock$/i,
    /yarn\.lock$/i,
    /\.min\.(js|css)$/i
];

/**
 * Read and parse JSON from stdin (async readline pattern).
 * @param {Object} options
 * @param {boolean} options.failClosed - If true, exit 2 on parse error (for security hooks). Default: false.
 * @returns {Promise<Object>} Parsed JSON event
 */
async function readStdin({ failClosed = false } = {}) {
    const rl = readline.createInterface({ input: process.stdin });
    let input = '';

    for await (const line of rl) {
        input += line;
    }

    if (!input || input.trim() === '') {
        if (failClosed) {
            console.error('Hook error: empty stdin input');
            process.exit(2);
        }
        process.stdout.write('{}');
        process.exit(0);
    }

    try {
        return JSON.parse(input);
    } catch (err) {
        if (failClosed) {
            console.error(`Hook error: invalid JSON input - ${err.message}`);
            process.exit(2);
        }
        process.stdout.write('{}');
        process.exit(0);
    }
}

/**
 * Parse file_path and content from a hook event.
 * @param {Object} event - Parsed hook JSON event
 * @returns {{ filePath: string, content: string }}
 */
function parseHookEvent(event) {
    const filePath = event.tool_input?.file_path || '';
    const content = event.tool_input?.content || event.tool_input?.new_string || '';
    return { filePath, content };
}

/**
 * Check if a file should be skipped based on extension and path patterns.
 * @param {string} filePath
 * @param {RegExp[]} extraPatterns - Additional skip patterns beyond the base set
 * @returns {boolean}
 */
function shouldSkipFile(filePath, extraPatterns = []) {
    if (!filePath) return true;

    const ext = filePath.substring(filePath.lastIndexOf('.')).toLowerCase();
    if (SKIP_EXTENSIONS.includes(ext)) return true;

    const allPatterns = [...SKIP_PATTERNS_BASE, ...extraPatterns];
    for (const pattern of allPatterns) {
        if (pattern.test(filePath)) return true;
    }

    return false;
}

/**
 * Check if a context pattern matches within N lines of a match position.
 * @param {string} content - Full file content
 * @param {number} matchIndex - Character index of the match
 * @param {RegExp} contextPattern - Pattern to search for nearby
 * @param {number} lineRadius - Number of lines above/below to check (default 3)
 * @returns {boolean}
 */
function hasNearbyContext(content, matchIndex, contextPattern, lineRadius = 3) {
    const lines = content.split('\n');
    let charCount = 0;
    let matchLine = 0;

    for (let i = 0; i < lines.length; i++) {
        charCount += lines[i].length + 1;
        if (charCount > matchIndex) {
            matchLine = i;
            break;
        }
    }

    const startLine = Math.max(0, matchLine - lineRadius);
    const endLine = Math.min(lines.length - 1, matchLine + lineRadius);
    const nearbyText = lines.slice(startLine, endLine + 1).join('\n');

    return contextPattern.test(nearbyText);
}

/**
 * Check if a matched value is in an allowlist.
 * @param {string} value - The matched string to check
 * @param {RegExp[]} patterns - Allowlist patterns
 * @returns {boolean}
 */
function isAllowlisted(value, patterns) {
    for (const pattern of patterns) {
        if (pattern.test(value)) return true;
    }
    return false;
}

/**
 * Deduplicate findings by type:masked key.
 * @param {{ type: string, masked: string }[]} findings
 * @returns {{ type: string, masked: string }[]}
 */
function deduplicateFindings(findings) {
    const unique = [];
    const seen = new Set();
    for (const finding of findings) {
        const key = `${finding.type}:${finding.masked}`;
        if (!seen.has(key)) {
            seen.add(key);
            unique.push(finding);
        }
    }
    return unique;
}

/**
 * Format findings for stderr display.
 * @param {{ type: string, masked: string }[]} findings
 * @param {number} limit - Max findings to show (default 5)
 * @returns {{ list: string, more: string }}
 */
function formatFindings(findings, limit = 5) {
    const list = findings
        .slice(0, limit)
        .map(f => `  - ${f.type}: ${f.masked}`)
        .join('\n');

    const more = findings.length > limit
        ? `\n  ...and ${findings.length - limit} more`
        : '';

    return { list, more };
}

/**
 * Allow the operation and exit.
 */
function allowAndExit() {
    process.stdout.write('{}');
    process.exit(0);
}

/**
 * Block the operation with an error message and exit.
 * @param {string} message - Error message shown to Claude
 */
function blockAndExit(message) {
    console.error(message);
    process.exit(2);
}

module.exports = {
    readStdin,
    parseHookEvent,
    shouldSkipFile,
    hasNearbyContext,
    isAllowlisted,
    deduplicateFindings,
    formatFindings,
    allowAndExit,
    blockAndExit,
    SKIP_EXTENSIONS,
    SKIP_PATTERNS_BASE
};
