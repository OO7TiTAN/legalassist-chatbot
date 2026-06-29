<?php
/**
 * LegalAssist Chatbot Proxy
 * 
 * Place this file in your WordPress theme directory or a simple plugin.
 * It acts as a secure bridge between the chat widget on the frontend
 * and your FastAPI backend, protecting your backend URL and API keys.
 * 
 * Installation:
 *   Option A (Theme): Copy to /wp-content/themes/YOUR-THEME/chatbot-proxy.php
 *   Option B (Plugin): Create /wp-content/plugins/legalassist-chatbot/legalassist-chatbot.php
 *                      and include this file.
 */

// ─── Configuration ────────────────────────────────────────────────────────────
// UPDATE THIS URL after deploying to Render:
define('LA_BACKEND_URL', 'https://legalassist-chatbot.onrender.com');

// Rate limiting (requests per minute per IP)
define('LA_RATE_LIMIT', 20);
define('LA_RATE_WINDOW', 60); // seconds

// ─── Bootstrap ───────────────────────────────────────────────────────────────
// Allow this file to run standalone (without WordPress bootstrap)
if (!defined('ABSPATH')) {
    // Not inside WordPress – load minimal config
    header('Content-Type: application/json');
} else {
    // Inside WordPress
    if (!defined('DOING_AJAX')) {
        header('Content-Type: application/json');
    }
}

// ─── CORS Headers ────────────────────────────────────────────────────────────
$allowed_origins = ['https://legalassist.co.uk', 'https://www.legalassist.co.uk'];
$origin = isset($_SERVER['HTTP_ORIGIN']) ? $_SERVER['HTTP_ORIGIN'] : '';

if (in_array($origin, $allowed_origins) || strpos($origin, 'localhost') !== false) {
    header('Access-Control-Allow-Origin: ' . $origin);
    header('Access-Control-Allow-Methods: POST, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type');
    header('Access-Control-Max-Age: 86400');
}

// Handle preflight
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// Only allow POST
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// ─── Rate Limiting ────────────────────────────────────────────────────────────
function la_get_client_ip() {
    $headers = ['HTTP_CF_CONNECTING_IP', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'REMOTE_ADDR'];
    foreach ($headers as $h) {
        if (!empty($_SERVER[$h])) {
            $ip = trim(explode(',', $_SERVER[$h])[0]);
            if (filter_var($ip, FILTER_VALIDATE_IP)) return $ip;
        }
    }
    return '0.0.0.0';
}

function la_check_rate_limit($ip) {
    $cache_key = 'la_rl_' . md5($ip);
    $cache_file = sys_get_temp_dir() . '/' . $cache_key . '.json';
    
    $data = ['count' => 0, 'window_start' => time()];
    if (file_exists($cache_file)) {
        $raw = file_get_contents($cache_file);
        if ($raw) {
            $saved = json_decode($raw, true);
            if ($saved && (time() - $saved['window_start']) < LA_RATE_WINDOW) {
                $data = $saved;
            }
        }
    }
    
    $data['count']++;
    file_put_contents($cache_file, json_encode($data));
    
    return $data['count'] <= LA_RATE_LIMIT;
}

$client_ip = la_get_client_ip();
if (!la_check_rate_limit($client_ip)) {
    http_response_code(429);
    echo json_encode(['error' => 'Too many requests. Please slow down.']);
    exit;
}

// ─── Request Validation ───────────────────────────────────────────────────────
$raw_body = file_get_contents('php://input');
if (!$raw_body) {
    http_response_code(400);
    echo json_encode(['error' => 'Empty request body']);
    exit;
}

$body = json_decode($raw_body, true);
if (json_last_error() !== JSON_ERROR_NONE) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON']);
    exit;
}

// Validate endpoint parameter
$endpoint = isset($_GET['endpoint']) ? trim($_GET['endpoint']) : '';
$allowed_endpoints = ['', '/collect-email', '/pageview'];
if (!in_array($endpoint, $allowed_endpoints)) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid endpoint']);
    exit;
}

// Basic message length validation
if (isset($body['message']) && strlen($body['message']) > 2000) {
    http_response_code(400);
    echo json_encode(['error' => 'Message too long']);
    exit;
}

// ─── Forward to Backend ───────────────────────────────────────────────────────
$backend_url = rtrim(LA_BACKEND_URL, '/') . '/chat' . $endpoint;

$context = stream_context_create([
    'http' => [
        'method'  => 'POST',
        'header'  => "Content-Type: application/json\r\nUser-Agent: LegalAssist-Proxy/1.0\r\n",
        'content' => json_encode($body),
        'timeout' => 30,
        'ignore_errors' => true,
    ],
    'ssl' => [
        'verify_peer' => true,
        'verify_peer_name' => true,
    ],
]);

$response_raw = @file_get_contents($backend_url, false, $context);
$http_status = 500;

if (isset($http_response_header)) {
    foreach ($http_response_header as $header) {
        if (preg_match('/^HTTP\/\d\.?\d?\s+(\d+)/', $header, $matches)) {
            $http_status = (int)$matches[1];
        }
    }
}

if ($response_raw === false) {
    http_response_code(502);
    echo json_encode(['error' => 'Backend connection failed. Please try again or call us on 0161 470 0727']);
    exit;
}

http_response_code($http_status);
header('Content-Type: application/json');
echo $response_raw;
