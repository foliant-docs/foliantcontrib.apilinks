# 1.2.1

-   Renamed `spec_url` to `spec` because it may also be a path to local file,
-   Improved swagger.json parsing
-   Added Redoc support (`redoc` site backend)

# 1.2.0

-   Added Swagger UI support,
-   Anchors are now generated properly, with header_anchors tool. Added `site_backend` optional param to determine for which backend the anchors should be generated.

# 1.1.3

-   Moved combined_options into a submodule

# 1.1.1

-   Added filename to warnings.

# 1.1.0

-   Prefixes are now case insensitive.
-   Only prefixes which are defined are trimmed.
-   New option `only-defined-prefixes` to ignore all prefixes which are not listed in config.
-   Options renamed and regrouped. Breaks backward compatibility.
-   Support of several reference pattern and properties (to catch models).
-   Now search on API page for headers h1, h2, h3 and h4.

# 1.0.5

-   Now both command and endpoint prefix are ensured to start from root (/).

# 1.0.4

-   Fix not catching errors from urllib.
-   Added 'ignoring-prefix' option.
-   Added 'endpoint-prefix' option into API->Name section.

# 1.0.3

-   Add require-prefix option.

# 1.0.2

-   Trim prefixes function.

# 1.0.1

-   Update docs, fix anchor error.
-   Add all HTTP verbs to regular expression.

# 1.0.0

-   Initial release.
