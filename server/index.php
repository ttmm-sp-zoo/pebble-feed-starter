<?php
/**
 * pebble-feed-starter — feed router (Pebble Appstore API format)
 * Serves data/ built by generate.py. Drop into your feed directory with .htaccess.
 * License: MIT
 */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

$ROOT = __DIR__;
$DIMS = array('aplite'=>'144x168','basalt'=>'144x168','diorite'=>'144x168','flint'=>'144x168','emery'=>'200x228','chalk'=>'180x180','gabbro'=>'260x260');

function fail($code, $msg) { http_response_code($code); echo json_encode(array('error'=>$msg)); exit; }

$index = json_decode(@file_get_contents($ROOT.'/data/index.json'), true);
if (!$index) fail(500, 'index.json missing — run generate.py and upload data/');
$BASEPATH = isset($index['base_path']) ? rtrim($index['base_path'], '/') : '';

$hardware = isset($_GET['hardware']) ? strtolower(preg_replace('/[^a-z]/', '', $_GET['hardware'])) : 'basalt';
$limit  = isset($_GET['limit'])  ? max(1, min(100, (int)$_GET['limit'])) : 20;
$offset = isset($_GET['offset']) ? max(0, (int)$_GET['offset']) : 0;
$sort   = isset($_GET['sort']) ? $_GET['sort'] : 'updated';

function plat_for($hw, $targets) {
    $map = array('flint'=>'diorite');                 // Core 2 Duo runs the diorite build
    $p = isset($map[$hw]) ? $map[$hw] : $hw;
    if (in_array($p, $targets)) return $p;
    if (in_array('basalt', $targets)) return 'basalt';
    return $targets ? $targets[0] : null;
}

function load_app($id, $hw) {
    global $ROOT, $DIMS;
    if (!preg_match('/^[a-f0-9]{24}$/', $id)) return null;
    $f = $ROOT.'/data/apps/'.$id.'.json';
    if (!file_exists($f)) return null;
    $a = json_decode(file_get_contents($f), true);
    $p = plat_for($hw, $a['_targets']);
    if ($p !== null) {
        if (!empty($a['_descs'][$p])) $a['description'] = $a['_descs'][$p];
        $dim = isset($DIMS[$p]) ? $DIMS[$p] : '144x168';
        $a['screenshot_hardware'] = $p;
        $a['screenshot_images'] = array();
        foreach ((isset($a['_screens'][$p]) ? $a['_screens'][$p] : array()) as $u) $a['screenshot_images'][] = array($dim => $u);
    }
    unset($a['_descs'], $a['_screens'], $a['_targets']);
    return $a;
}

function reply($data, $limit, $offset, $base) {
    $page = array_slice($data, $offset, $limit);
    $next = ($offset + $limit < count($data)) ? ($base.'?limit='.$limit.'&offset='.($offset+$limit)) : null;
    echo json_encode(array('data'=>array_values($page), 'limit'=>$limit, 'offset'=>$offset, 'links'=>array('nextPage'=>$next)), JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
    exit;
}

function sort_ids($ids, $sort) {
    global $index;
    if ($sort !== 'hearts') return $ids;
    $h = array(); foreach ($index['apps'] as $a) $h[$a['id']] = $a['hearts'];
    usort($ids, function($x, $y) use ($h) { return $h[$y] - $h[$x]; });
    return $ids;
}

$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if (!preg_match('#/api/v1/(.+)$#', $uri, $mm)) {
    // Not an API call. Apache serves this file as the directory index, so this is a
    // person opening the feed root in a browser. Give them the one thing they need:
    // the source address (base_url + /api), as a one-tap link and as text to paste.
    $base   = isset($index['base_url']) ? rtrim($index['base_url'], '/') : '';
    $source = $base . '/api';
    $name   = isset($index['developer']['name']) ? $index['developer']['name'] : 'Feed';
    $deep   = 'pebble://add-store-feed/' . rawurlencode($name) . '/' . rawurlencode($source);
    $h = function($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); };
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<title>' . $h($name) . ' - Pebble appstore source</title>'
       . '<style>body{font:16px/1.6 system-ui,-apple-system,sans-serif;margin:3rem auto;max-width:38rem;'
       . 'padding:0 1rem;color:#111}a.btn{display:inline-block;padding:.7em 1.2em;background:#111;color:#fff;'
       . 'border-radius:6px;text-decoration:none}code{background:#eee;padding:.1em .3em}ul{padding-left:1.2em}</style>'
       . '<h1>' . $h($name) . '</h1>'
       . '<p>An appstore source for the Pebble app.</p>'
       . '<p><a class="btn" href="' . $h($deep) . '">Add to the Pebble app</a></p>'
       . '<p>Or by hand: <b>Appstore Sources &rarr; Add Source</b>, paste <code>' . $h($source) . '</code></p>'
       . '<p>What this feed serves:</p><ul>'
       . '<li><a href="' . $h($base) . '/data/index.json">data/index.json</a> - the generated feed as plain files</li>'
       . '<li><a href="' . $h($base) . '/api/v1/apps/dev/x">api/v1/apps/dev/x</a> - the whole catalog through the router</li>'
       . '<li><a href="' . $h($base) . '/api/v1/home/watchfaces">api/v1/home/watchfaces</a> - the home payload</li>'
       . '</ul><p style="color:#666;font-size:.9em">Served by <a href="https://github.com/ttmm-sp-zoo/pebble-feed-starter">pebble-feed-starter</a> (MIT). Edit this page in <code>index.php</code>.</p>';
    exit;
}
$parts = explode('/', rtrim($mm[1], '/'));

if ($parts[0]==='apps' && isset($parts[1]) && $parts[1]==='id' && isset($parts[2])) {
    $a = load_app($parts[2], $hardware); if (!$a) fail(404, 'app not found');
    echo json_encode(array('data'=>array($a), 'limit'=>1, 'offset'=>0, 'links'=>array('nextPage'=>null)), JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE); exit;
}
if ($parts[0]==='apps' && isset($parts[1]) && $parts[1]==='bulk') {
    $body = json_decode(file_get_contents('php://input'), true);
    $ids = (isset($body['ids']) && is_array($body['ids'])) ? array_slice($body['ids'], 0, 500) : array();
    if (isset($body['hardware'])) $hardware = strtolower($body['hardware']);
    $out=array(); $missing=array();
    foreach ($ids as $id) { $a=load_app($id,$hardware); if($a)$out[]=$a; else $missing[]=$id; }
    echo json_encode(array('data'=>$out, 'missing'=>$missing), JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE); exit;
}
if ($parts[0]==='apps' && isset($parts[1]) && ($parts[1]==='dev' || $parts[1]==='category')) {
    $ids = sort_ids(array_map(function($a){return $a['id'];}, $index['apps']), $sort);
    $apps=array(); foreach($ids as $id) $apps[]=load_app($id,$hardware);
    reply($apps, $limit, $offset, $BASEPATH.'/api/v1/'.$parts[1].'/'.(isset($parts[2])?$parts[2]:''));
}
if ($parts[0]==='apps' && isset($parts[1]) && $parts[1]==='collection' && isset($parts[2])) {
    $kol=null; foreach($index['collections'] as $k) if($k['slug']===$parts[2]){$kol=$k;break;}
    if(!$kol) fail(404,'collection not found');
    $supports=array();
    foreach($index['apps'] as $a){ $t=$a['targets'];
        if(in_array($hardware,$t) || ($hardware==='flint'&&in_array('diorite',$t)) || !in_array($hardware,array('aplite','basalt','chalk','diorite','flint','emery','gabbro'))) $supports[$a['id']]=true; }
    $ids=array_values(array_filter($kol['application_ids'], function($id) use ($supports){return isset($supports[$id]);}));
    $ids=sort_ids($ids,$sort);
    $apps=array(); foreach($ids as $id) $apps[]=load_app($id,$hardware);
    reply($apps, $limit, $offset, $BASEPATH.'/api/v1/apps/collection/'.$parts[2].'/'.(isset($parts[3])?$parts[3]:'watchfaces'));
}
if ($parts[0]==='home') {
    $cols=array();
    foreach($index['collections'] as $k)
        $cols[]=array('slug'=>$k['slug'],'name'=>$k['name'],'application_ids'=>$k['application_ids'],
                      'links'=>array('apps'=>$BASEPATH.'/api/v1/apps/collection/'.$k['slug'].'/watchfaces'));
    $fids=array_slice(sort_ids(array_map(function($a){return $a['id'];},$index['apps']),'hearts'),0,$limit);
    $feat=array(); foreach($fids as $id) $feat[]=load_app($id,$hardware);
    echo json_encode(array('banners'=>array(),
        'categories'=>array(array('id'=>$index['category']['id'],'name'=>$index['category']['name'],'slug'=>$index['category']['slug'],'color'=>$index['category']['color'])),
        'collections'=>$cols,'onboarding'=>$index['onboarding'],'data'=>$feat,
        'limit'=>$limit,'offset'=>$offset,'links'=>array('nextPage'=>null)), JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);
    exit;
}
fail(404, 'not found');
