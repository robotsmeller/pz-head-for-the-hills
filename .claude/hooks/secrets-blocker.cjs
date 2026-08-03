#!/usr/bin/env node
/**
 * Secrets Blocker Hook
 * Prevents accidental commit of API keys, passwords, and other secrets.
 *
 * Event: PreToolUse
 * Tool: Edit, Write
 *
 * Detects:
 * - AWS access keys and secrets
 * - GitHub/GitLab tokens
 * - Stripe API keys (live only - test keys allowed)
 * - Supabase service role keys
 * - Generic API keys (high-entropy strings)
 * - Private keys (RSA, DSA, EC, PGP)
 * - Database connection strings with passwords
 * - Password assignments in code
 * - JWT tokens
 * - Base64-encoded secrets (decoded and rescanned)
 * - String concatenation of known secret prefixes
 */

const {
    readStdin,
    parseHookEvent,
    shouldSkipFile,
    hasNearbyContext,
    isAllowlisted,
    deduplicateFindings,
    formatFindings,
    allowAndExit,
    blockAndExit
} = require('./hook-utils.cjs');

const EXTRA_SKIP_PATTERNS = [
    /\.example$/i,
    /\.sample$/i,
    /\.template$/i
];

const ALLOWLIST_PATTERNS = [
    /^your[_-]?(api)?[_-]?key$/i,
    /^xxx+$/i,
    /^placeholder$/i,
    /^changeme$/i,
    /^secret$/i,
    /^password$/i,
    /^sk[_-]test[_-]/i,
    /^pk[_-]test[_-]/i,
    /^example$/i,
    /^test[_-]?key$/i,
    /^dummy$/i,
    /^fake$/i,
    /^sample$/i,
    /^demo$/i,
    /<[^>]+>/,
    /\$\{[^}]+\}/,
    /\{\{[^}]+\}\}/,
    /process\.env\./i,
    /import\.meta\.env\./i,
    /Deno\.env\./i,
];

const BASE64_RESCAN_PATTERNS = [
    /AKIA[0-9A-Z]{16}/,
    /ghp_[A-Za-z0-9]{36}/,
    /gho_[A-Za-z0-9]{36}/,
    /ghu_[A-Za-z0-9]{36}/,
    /ghs_[A-Za-z0-9]{36}/,
    /glpat-[A-Za-z0-9_-]{20,}/,
    /sk_live_[A-Za-z0-9]{24,}/,
    /pk_live_[A-Za-z0-9]{24,}/,
    /xox[baprs]-[0-9A-Za-z-]{10,}/,
    /SG\.[A-Za-z0-9_-]{22}\./,
    /-----BEGIN.*PRIVATE KEY-----/,
    /npm_[A-Za-z0-9]{36}/,
    /AIza[0-9A-Za-z_-]{35}/,
    /sbp_[A-Za-z0-9]{40}/,
    /sk-ant-[A-Za-z0-9_-]{40,}/,
    /re_[A-Za-z0-9]{32,}/,
];

const SECRET_PATTERNS = [
    { name: 'AWS Access Key ID', pattern: /\b(AKIA[0-9A-Z]{16})\b/g, description: 'AWS access key (starts with AKIA)' },
    { name: 'AWS Secret Access Key', pattern: /\b([A-Za-z0-9/+=]{40})\b/g, context: /aws[_-]?secret|secret[_-]?access[_-]?key/i, description: 'AWS secret key (40 char base64)' },
    { name: 'GitHub Personal Access Token', pattern: /\b(ghp_[A-Za-z0-9]{36})\b/g, description: 'GitHub PAT (starts with ghp_)' },
    { name: 'GitHub OAuth Token', pattern: /\b(gho_[A-Za-z0-9]{36})\b/g, description: 'GitHub OAuth (starts with gho_)' },
    { name: 'GitHub App Token', pattern: /\b(ghu_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36})\b/g, description: 'GitHub App token' },
    { name: 'GitLab Token', pattern: /\b(glpat-[A-Za-z0-9_-]{20,})\b/g, description: 'GitLab personal access token' },
    { name: 'Stripe Live Secret Key', pattern: /\b(sk_live_[A-Za-z0-9]{24,})\b/g, description: 'Stripe live secret key' },
    { name: 'Stripe Live Publishable Key', pattern: /\b(pk_live_[A-Za-z0-9]{24,})\b/g, description: 'Stripe live publishable key' },
    { name: 'Supabase Service Role Key', pattern: /\b(sbp_[A-Za-z0-9]{40,})\b/g, description: 'Supabase service role or access token' },
    { name: 'Slack Token', pattern: /\b(xox[baprs]-[0-9A-Za-z-]{10,})\b/g, description: 'Slack API token' },
    { name: 'Discord Token', pattern: /\b([MN][A-Za-z0-9]{23,}\.[\w-]{6}\.[\w-]{27})\b/g, description: 'Discord bot/user token' },
    { name: 'Twilio API Key', pattern: /\b(SK[0-9a-fA-F]{32})\b/g, description: 'Twilio API key' },
    { name: 'SendGrid API Key', pattern: /\b(SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43})\b/g, description: 'SendGrid API key' },
    { name: 'Generic API Key', pattern: /\b(?:api[_-]?key|apikey|api[_-]?secret|secret[_-]?key)\s*[:=]\s*(['"]?)([A-Za-z0-9_-]{20,})\1/gi, description: 'Generic API key assignment' },
    { name: 'Private Key', pattern: /-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----/gi, description: 'RSA/DSA/EC private key' },
    { name: 'PGP Private Key', pattern: /-----BEGIN\s+PGP\s+PRIVATE\s+KEY\s+BLOCK-----/gi, description: 'PGP private key block' },
    { name: 'Database Connection String', pattern: /(?:mysql|postgres|postgresql|mongodb|redis):\/\/[^:]+:([^@\s]+)@/gi, description: 'Database URL with password' },
    {
        name: 'Password Assignment', pattern: /\b(?:password|passwd|pwd)\s*[:=]\s*['"]([^'"]{8,})['"]/gi,
        validator: (match) => {
            const lower = match.toLowerCase();
            return !['password', 'changeme', 'secret', 'test', 'example', 'placeholder'].some(p => lower.includes(p));
        },
        description: 'Hardcoded password'
    },
    {
        name: 'JWT Token', pattern: /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g,
        validator: (match) => {
            try {
                const payload = match.split('.')[1];
                const decoded = Buffer.from(payload.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8');
                const parsed = JSON.parse(decoded);
                const testValues = ['test', 'example', 'demo', 'fake', 'sample', 'localhost'];
                const sub = (parsed.sub || '').toLowerCase();
                const iss = (parsed.iss || '').toLowerCase();
                if (testValues.some(t => sub.includes(t) || iss.includes(t))) return false;
            } catch { /* not decodable - still flag */ }
            return true;
        },
        description: 'JSON Web Token (skips test/example payloads)'
    },
    { name: 'Bearer Token', pattern: /\bBearer\s+([A-Za-z0-9_-]{20,})\b/gi, description: 'Bearer authentication token' },
    { name: 'Google API Key', pattern: /\bAIza[0-9A-Za-z_-]{35}\b/g, description: 'Google API key' },
    { name: 'Firebase Key', pattern: /\bAAAA[A-Za-z0-9_-]{7}:[A-Za-z0-9_-]{140}\b/g, description: 'Firebase Cloud Messaging key' },
    { name: 'Anthropic API Key', pattern: /\b(sk-ant-[A-Za-z0-9_-]{40,})\b/g, description: 'Anthropic Claude API key' },
    { name: 'Resend API Key', pattern: /\b(re_[A-Za-z0-9]{32,})\b/g, description: 'Resend transactional email API key' },
    { name: 'npm Token', pattern: /\b(npm_[A-Za-z0-9]{36})\b/g, description: 'npm access token' },
    { name: 'Heroku API Key', pattern: /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, context: /heroku/i, description: 'Heroku API key (UUID format)' },
    {
        name: 'Base64-Encoded Secret', pattern: /\b[A-Za-z0-9+/]{40,}={0,2}\b/g,
        validator: (match) => {
            try {
                const decoded = Buffer.from(match, 'base64').toString('utf8');
                if (!/^[\x20-\x7E\n\r\t]+$/.test(decoded)) return false;
                return BASE64_RESCAN_PATTERNS.some(p => p.test(decoded));
            } catch { return false; }
        },
        description: 'Base64-encoded secret (decoded and rescanned)'
    },
    { name: 'Concatenated Secret Prefix', pattern: /['"](?:sk_|pk_|ghp_|gho_|ghu_|ghs_|glpat-|xox[baprs]-|npm_|AKIA|AIza|sbp_)['"]\s*\+/g, description: 'Secret prefix in string concatenation' }
];

function detectSecrets(content, filePath) {
    const findings = [];

    for (const secret of SECRET_PATTERNS) {
        secret.pattern.lastIndex = 0;

        for (const m of content.matchAll(secret.pattern)) {
            const match = m[0];

            if (secret.context && !hasNearbyContext(content, m.index, secret.context)) continue;

            const actual = match.replace(/^.*[:=]\s*['"]?/, '').replace(/['"]?\s*$/, '');

            if (isAllowlisted(actual, ALLOWLIST_PATTERNS) || isAllowlisted(match, ALLOWLIST_PATTERNS)) continue;
            if (secret.validator && !secret.validator(actual)) continue;

            const toMask = actual.length > 8 ? actual : match;
            const masked = toMask.length > 10
                ? toMask.substring(0, 4) + '*'.repeat(Math.min(toMask.length - 8, 16)) + toMask.substring(toMask.length - 4)
                : '***';

            findings.push({ type: secret.name, masked, description: secret.description });
        }
    }

    return deduplicateFindings(findings);
}

async function main() {
    const event = await readStdin({ failClosed: true });
    const { filePath, content } = parseHookEvent(event);

    if (shouldSkipFile(filePath, EXTRA_SKIP_PATTERNS)) allowAndExit();
    if (!content || content.trim() === '') allowAndExit();

    const findings = detectSecrets(content, filePath);

    if (findings.length > 0) {
        const { list, more } = formatFindings(findings);
        blockAndExit(
            `Blocked: Potential secrets detected in ${filePath}\n\nFindings:\n${list}${more}\n\n` +
            `Best practices:\n` +
            `- Use environment variables: process.env.API_KEY\n` +
            `- Use .env files (add to .gitignore)\n` +
            `- For test keys, use sk_test_ or pk_test_ prefixes\n` +
            `- Store credentials in c:\\xampp\\htdocs\\.credentials\\`
        );
    }

    allowAndExit();
}

main().catch(err => {
    console.error(`secrets-blocker error: ${err.message}`);
    process.exit(2);
});
