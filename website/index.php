<?php
declare(strict_types=1);

$repository = 'https://github.com/ediril/hlsync';
$year = (int) date('Y');
$title = 'HLSync — a better way to "just FTP it"';
$description = 'Map your local project once. Preview the diff. Push exactly what you intend to shared hosting over FTPS.';
$requestHost = (string) ($_SERVER['HTTP_HOST'] ?? '');
$validHost = preg_match('/\A[a-z0-9.-]+(?::[0-9]+)?\z/i', $requestHost) === 1;
$forwardedProtocol = strtolower((string) ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? ''));
$secureRequest = (
    strtolower((string) ($_SERVER['HTTPS'] ?? '')) === 'on'
    || $forwardedProtocol === 'https'
);
$requestPath = parse_url((string) ($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH);
$pagePath = is_string($requestPath) && str_starts_with($requestPath, '/')
    ? $requestPath
    : '/';
$origin = $validHost
    ? ($secureRequest ? 'https://' : 'http://') . $requestHost
    : null;
$canonicalUrl = $origin === null ? null : $origin . $pagePath;
$socialImageUrl = $origin === null
    ? null
    : $origin . '/assets/social-preview.jpg';
$structuredData = [
    '@context' => 'https://schema.org',
    '@type' => 'SoftwareApplication',
    'name' => 'HLSync',
    'description' => $description,
    'applicationCategory' => 'DeveloperApplication',
    'operatingSystem' => 'Any operating system with Python 3.10+',
    'url' => $canonicalUrl ?? $repository,
    'downloadUrl' => 'https://pypi.org/project/hlsync/',
    'sameAs' => $repository,
    'license' => $repository . '/blob/main/LICENSE',
    'offers' => [
        [
            '@type' => 'Offer',
            'name' => 'PolyForm Strict license',
            'description' => 'No charge for uses permitted by PolyForm Strict 1.0.0. Listed personal uses must have no anticipated commercial application. The license also permits use by listed organizations. No rights to modify, redistribute, or create works based on HLSync are granted.',
            'price' => '0',
            'priceCurrency' => 'USD',
            'url' => $repository . '/blob/main/LICENSE',
        ],
        [
            '@type' => 'Offer',
            'name' => 'Commercial license',
            'description' => 'Commercial use outside the permissions of PolyForm Strict 1.0.0 requires a separate paid agreement before use. Contact emrah@diril.org for pricing.',
            'url' => ($canonicalUrl ?? $repository) . '#pricing',
        ],
    ],
];
if ($socialImageUrl !== null) {
    $structuredData['image'] = $socialImageUrl;
}
$structuredDataJson = json_encode(
    $structuredData,
    JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT
        | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
);
if ($structuredDataJson === false) {
    throw new RuntimeException('Could not encode website structured data.');
}

function h(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#080b10">
    <meta name="description" content="<?= h($description) ?>">
    <meta name="robots" content="index, follow, max-image-preview:large">
    <meta name="author" content="HLSync contributors">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="en_US">
    <meta property="og:site_name" content="HLSync">
    <meta property="og:title" content="<?= h($title) ?>">
    <meta property="og:description" content="<?= h($description) ?>">
<?php if ($canonicalUrl !== null && $socialImageUrl !== null): ?>
    <link rel="canonical" href="<?= h($canonicalUrl) ?>">
    <meta property="og:url" content="<?= h($canonicalUrl) ?>">
    <meta property="og:image" content="<?= h($socialImageUrl) ?>">
<?php if ($secureRequest): ?>
    <meta property="og:image:secure_url" content="<?= h($socialImageUrl) ?>">
<?php endif; ?>
<?php endif; ?>
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="HLSync terminal workflow: diff local files, then push over FTPS.">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="<?= h($title) ?>">
    <meta name="twitter:description" content="<?= h($description) ?>">
<?php if ($socialImageUrl !== null): ?>
    <meta name="twitter:image" content="<?= h($socialImageUrl) ?>">
    <meta name="twitter:image:alt" content="HLSync terminal workflow: diff local files, then push over FTPS.">
<?php endif; ?>
    <script type="application/ld+json"><?= $structuredDataJson ?></script>
    <title><?= h($title) ?></title>
    <link rel="describedby" href="/llms.txt" type="text/markdown">
    <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
    <link rel="icon" href="assets/favicon-32x32.png" type="image/png" sizes="32x32">
    <link rel="shortcut icon" href="favicon.ico">
    <link rel="apple-touch-icon" href="assets/apple-touch-icon.png" sizes="180x180">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&amp;family=Space+Mono:wght@400;700&amp;display=swap" rel="stylesheet">
    <link rel="stylesheet" href="assets/site.css">
    <script src="assets/site.js" defer></script>
</head>
<body>
    <a class="skip-link" href="#main">Skip to content</a>

    <header class="site-header" data-header>
        <a class="brand" href="#top" aria-label="HLSync home">
            <svg class="brand-mark" viewBox="0 0 48 48" aria-hidden="true">
                <path d="M14 7v24a10 10 0 0 0 20 0V20" />
                <path d="m29 25 5-5 5 5" />
                <circle cx="14" cy="7" r="3" />
            </svg>
            <span>HL<span>Sync</span></span>
        </a>

        <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav" data-nav-toggle>
            <span></span><span></span>
            <span class="sr-only">Toggle navigation</span>
        </button>

        <nav class="site-nav" id="site-nav" aria-label="Primary navigation" data-nav>
            <a href="#workflow">Workflow</a>
            <a href="#principles">Safety</a>
            <a href="#pricing">Licensing &amp; pricing</a>
            <a class="nav-cta" href="<?= h($repository) ?>">GitHub <span aria-hidden="true">↗</span></a>
        </nav>
    </header>

    <main id="main">
        <section class="hero" id="top">
            <div class="hero-copy">
                <p class="eyebrow"><span class="signal"></span> PRE-ALPHA</p>
                <h1>A better way to<br><span>“just FTP it.”</span></h1>
                <p class="hero-lede">
                    Map your local project once. Preview the diff. Push exactly what
                    you intend to shared hosting over FTPS.
                </p>

                <div class="hero-actions">
                    <div class="install-command" aria-label="Installation command">
                        <span aria-hidden="true">$</span>
                        <code>pip install hlsync</code>
                        <button type="button" data-copy="pip install hlsync">
                            <span data-copy-label>copy</span>
                        </button>
                    </div>
                    <a class="text-link" href="#workflow">See the workflow <span aria-hidden="true">↓</span></a>
                </div>

                <div class="hero-meta" aria-label="Project metadata">
                    <div><span class="meta-label">transport</span><span class="meta-value">FTPS / explicit TLS</span></div>
                    <div><span class="meta-label">runtime</span><span class="meta-value">Python 3.10+</span></div>
                    <div><span class="meta-label">license</span><span class="meta-value">PolyForm Strict</span></div>
                </div>
            </div>

            <div class="terminal-wrap" aria-label="Example HLSync terminal session">
                <div class="terminal-glow"></div>
                <div class="terminal">
                    <div class="terminal-bar">
                        <div class="terminal-dots" aria-hidden="true"><i></i><i></i><i></i></div>
                        <span>~/sites/discovery — hlsync</span>
                        <span class="terminal-state">TLS:ON</span>
                    </div>
                    <div class="terminal-body">
                        <p><span class="prompt">❯</span> <b>hlsync diff -p</b></p>
                        <p class="muted">Checking differences for profile 'discovery'...</p>
                        <p><span class="directory">&nbsp; assets/</span></p>
                        <p><span class="added">+&nbsp; l</span> &nbsp; index.php</p>
                        <p><span class="removed">-&nbsp; r</span> &nbsp; legacy.php</p>
                        <p><span class="changed">~</span> &nbsp; &nbsp; &nbsp;site.css</p>
                        <p><span class="added">+&nbsp; l</span> <span class="directory">icons/</span></p>
                        <p class="terminal-gap"><span class="prompt">❯</span> <b>hlsync push -p</b></p>
                        <p class="muted">Pushing changes...</p>
                        <p>&nbsp; <span class="added">+</span> index.php</p>
                        <p>&nbsp; <span class="changed">~</span> site.css</p>
                        <p>&nbsp; <span class="added">+</span> <span class="directory">icons/</span></p>
                        <p>&nbsp; <span class="removed">-</span> legacy.php</p>
                        <p><span class="success">✓</span> Push complete: 4 changes.</p>
                        <span class="cursor" aria-hidden="true"></span>
                    </div>
                </div>
                <span class="coordinate coordinate-a">41.8781° N</span>
                <span class="coordinate coordinate-b">SYNC_CHANNEL_01</span>
            </div>
        </section>

        <section class="ticker" aria-label="Product attributes">
            <div>
                <span>MAP ONCE</span><i>◆</i><span>DIFF FIRST</span><i>◆</i>
                <span>PUSH FILES</span><i>◆</i><span>PUSH EXACTLY</span><i>◆</i>
                <span>MAP ONCE</span><i>◆</i><span>DIFF FIRST</span><i>◆</i>
            </div>
        </section>

        <section class="section workflow" id="workflow">
            <div class="section-heading">
                <p class="eyebrow">01 // THE LOOP</p>
                <h2>Map it once. Check the diff. Push.</h2>
                <p>HLSync remembers where the project lives locally and remotely, then shows what will change before any files move.</p>
            </div>

            <ol class="workflow-grid">
                <li>
                    <span class="step-number">01</span>
                    <div class="step-icon" aria-hidden="true">⌖</div>
                    <h3>Map the project</h3>
                    <p>Connect the current local directory to its remote root. HLSync recognizes that project from any directory beneath it.</p>
                    <code>hlsync create prod --host …</code>
                </li>
                <li>
                    <span class="step-number">02</span>
                    <div class="step-icon" aria-hidden="true">⌁</div>
                    <h3>Exclude what doesn’t belong</h3>
                    <p>Exclude files that should never leave your machine. Use an explicit pattern when future matching files should stay excluded too.</p>
                    <code>hlsync exclude --pattern '*.map'</code>
                </li>
                <li>
                    <span class="step-number">03</span>
                    <div class="step-icon" aria-hidden="true">∆</div>
                    <h3>Read the diff</h3>
                    <p>Compare local and remote files before changing either side. Routine output shows only what the push would change; <code>-x</code> adds exclusions and <code>--all</code> reveals the complete comparison.</p>
                    <code>hlsync diff</code>
                </li>
                <li>
                    <span class="step-number">04</span>
                    <div class="step-icon" aria-hidden="true">↥</div>
                    <h3>Push the changes</h3>
                    <p>Upload new and modified files. Nothing is deleted unless you add <code>-p</code> to remove remote-only files in the selected scope.</p>
                    <code>hlsync push</code>
                </li>
            </ol>
        </section>

        <section class="section principles" id="principles">
            <div class="section-heading split-heading">
                <div>
                    <p class="eyebrow">02 // DESIGN SIGNAL</p>
                    <h2>Safer than manual FTP.<br>Lighter than a deployment stack.</h2>
                </div>
                <p>HLSync keeps the familiar FTPS server you already have, while adding the project context, change preview, and deletion safeguards manual uploads are missing.</p>
            </div>

            <div class="principle-grid">
                <article class="principle principle-wide">
                    <span class="principle-index">A</span>
                    <div>
                        <h3>Local files drive the sync</h3>
                        <p>The remote is treated as a deployment target. A file missing locally is reported instead of being copied back unexpectedly.</p>
                    </div>
                    <div class="mini-diff" aria-hidden="true">
                        <span class="added">+&nbsp; l</span><i></i><b>local-only / added</b>
                        <span class="changed">~</span><i></i><b>changed</b>
                        <span class="remote-only">r</span><i></i><b>remote-only / kept</b>
                        <span class="removed">-&nbsp; r</span><i></i><b>deleted with -p</b>
                    </div>
                </article>
                <article class="principle">
                    <span class="principle-index">B</span>
                    <h3>Deletion is explicit</h3>
                    <p>Push never deletes by default. With <code>-p</code>, remote-only paths in the selected scope are deleted after uploads succeed.</p>
                </article>
                <article class="principle">
                    <span class="principle-index">C</span>
                    <h3>Path rules stay readable</h3>
                    <p>Quoted and unquoted wildcards select the same existing files. <code>--pattern</code> clearly marks rules that should match future files.</p>
                </article>
                <article class="principle principle-accent">
                    <span class="principle-index">D</span>
                    <h3>Verified FTPS connections</h3>
                    <p>HLSync verifies certificates, protects the data channel, and uses structured server listings over explicit TLS.</p>
                    <svg viewBox="0 0 160 80" aria-hidden="true"><path d="M4 60h34l15-36 28 46 19-30 14 20h42" /></svg>
                </article>
            </div>
        </section>

        <section class="section pricing" id="pricing" aria-labelledby="pricing-title">
            <div class="section-heading">
                <p class="eyebrow">03 // LICENSING &amp; PRICING</p>
                <h2 id="pricing-title">Use under PolyForm Strict.<br>Commercial licensing available.</h2>
                <p>PolyForm Strict 1.0.0 defines the uses available at no charge. Commercial use outside those permissions requires a separate paid agreement.</p>
            </div>

            <div class="pricing-grid">
                <article class="license-card" aria-labelledby="noncommercial-title">
                    <p class="license-label">POLYFORM STRICT 1.0.0</p>
                    <h3 id="noncommercial-title">Free</h3>
                    <p class="license-description">No charge for uses permitted by the license:</p>
                    <ul class="license-features">
                        <li>Any noncommercial purpose</li>
                        <li>Listed personal uses, such as study and hobby projects, without any anticipated commercial application</li>
                        <li>Use by the organizations listed in the license</li>
                        <li>No rights to modify, redistribute, or create works based on HLSync are granted</li>
                    </ul>
                    <a class="text-link" href="<?= h($repository) ?>/blob/main/LICENSE">Read the free license <span aria-hidden="true">↗</span></a>
                </article>

                <article class="license-card license-card-commercial" aria-labelledby="commercial-title">
                    <p class="license-label">COMMERCIAL</p>
                    <h3 id="commercial-title">Contact for pricing</h3>
                    <p class="license-description">For commercial use outside the free license's permissions, including:</p>
                    <ul class="license-features">
                        <li>Internal business deployments</li>
                        <li>Client work and paid services</li>
                        <li>Commercial products and hosted services</li>
                    </ul>
                    <a class="button-primary" href="mailto:emrah@diril.org?subject=HLSync%20commercial%20license">Request a commercial license <span aria-hidden="true">↗</span></a>
                    <p class="license-agreement">A separate paid agreement is required before commercial use outside the free license's permissions.</p>
                </article>
            </div>

            <p class="licensing-note">PolyForm Strict expressly permits use by listed organizations, such as charitable organizations, educational institutions, and government institutions, regardless of funding source or obligations resulting from funding. The <a href="<?= h($repository) ?>/blob/main/LICENSE">full license</a> governs; this summary grants no additional permissions. Unsure which applies? <a href="mailto:emrah@diril.org?subject=HLSync%20licensing%20question">Ask Emrah Diril</a>.</p>
        </section>
    </main>

    <footer class="site-footer">
        <a class="brand footer-brand" href="#top">HL<span>Sync</span></a>
        <p>Built for the narrow gap between “just FTP it” and deployment infrastructure.</p>
        <p>© <?= h((string) $year) ?> HLSync contributors // <a href="#pricing">Licensing &amp; pricing</a> // <a href="https://pypi.org/project/hlsync/">Latest release on PyPI ↗</a></p>
    </footer>
</body>
</html>
