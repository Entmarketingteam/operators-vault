/**
 * Injects Vercel env into index.html at build time.
 * Set SUPABASE_ANON_KEY (and optionally SUPABASE_URL) in Vercel → Settings → Environment Variables.
 */
const fs = require('fs');
const path = require('path');

const indexPath = path.join(__dirname, 'index.html');
let html = fs.readFileSync(indexPath, 'utf8');

const anonKey = process.env.SUPABASE_ANON_KEY || '';
const supabaseUrl = process.env.SUPABASE_URL || '';

if (anonKey) {
  const escaped = anonKey.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  html = html.replace('supabaseAnonKey: ""', 'supabaseAnonKey: "' + escaped + '"');
}
if (supabaseUrl) {
  const escaped = supabaseUrl.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  html = html.replace(/supabaseUrl:\s*"https:[^"]*"/, 'supabaseUrl: "' + escaped + '"');
}

fs.writeFileSync(indexPath, html);
console.log('Injected Supabase config into index.html');
