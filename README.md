![](https://img.shields.io/pypi/v/foliantcontrib.apilinks.svg)

# apilinks Preprocessor for Foliant

Preprocessor for replacing API *reference*s in markdown files with links to actual method description on the API documentation web-page.

## Installation

```shell
$ pip install foliantcontrib.apilinks
```

## Quick Start

Say, you have an API documentation hosted at the url http://example.com/api-docs

It may be a [Swagger UI](https://swagger.io/tools/swagger-ui/) website or just some static one-page site (like [Slate](https://github.com/slatedocs/slate)).

So if you have a site with API docs, you probably reference to them from time in your other documents:

```
To authenticate user use API method `GET /user/authenticate`.
```

We thought, how cool it'd be if this fragment: **\`GET /user/authenticate\`** automatically transformed into link to this method description on your API docs website. That's what APILinks is for.

Add it to your preprocessor list like this if your API docs is a Slate-like static website:

```yaml
preprocessors:
    - apilinks:
        API:
            My-API:
                url: http://example.com/api-docs
```

Or like this if your API docs is a Swagger UI website:

```yaml
preprocessors:
    - apilinks:
        API:
            My-API:
                url: http://example.com/api-docs
                spec: http://example.com/api-docs/swagger.json
```

Here:

- `API` is a required section;
- `My-API` is a local name of your API. Right now it is not very important but will come in handy in the next example;
- `url` is a string with full url to your API documentation web-page. It will be used to validate references and to construct a link to method;
- `spec` is a string with full url to OpenAPI specification file, which will be used to construct the proper anchor for the method. It may also be a path to local specification file if you don't want to download it each time.

After foliant applies the preprocessor your document will be transformed into this:

```
To authenticate user use API method [GET user/authenticate](http://example.com/api-docs/#get-user-authenticate).
```

Notice that preprocessor figured out the correct anchor `#get-user-authenticate` by himself. Now instead of plain name of the method you've got a link to the method description!

Ok, what if I have two different APIs: client API and admin API?

No problem, put both of them into your config:

```yaml
preprocessors:
    - apilinks:
        API:
            Client-API:
                url: http://example.com/client/api-docs
            Admin-API:
                url: http://example.com/admin/api-docs
                spec: http://example.com/admin/api-docs/swagger.yml
```

Now this source:

```
To authenticate user use API method `GET user/authenticate`.
To ban user from the website use admin API method `POST admin/ban_user/{user_id}`
```

Will be transformed by apilinks into this:

```
To authenticate user use API method [GET user/authenticate](http://example.com/client/api-docs/#get-user-authenticate).
To ban user from the website use admin API method [POST admin/ban_user/{user_id}](http://example.com/admin/api-docs/#/user/banUser)
```

Notice that apilinks determined that the first reference is from Client API, and the second one is from the Admin API. How is that possible? Preprocessor parses each API url from the config and stores their methods before looking for references. When the time comes to process the references it already has a list of all methods to validate your reference and to determine which API link should be inserted.

But what if we have the same-named method in both of our APIs? In this case you will see a warning:

```
WARNING: GET /service/healthcheck is present in several APIs (Client-API, Admin-API). Please, use prefix. Skipping
```

It suggests us to use prefix, and by that it means to prefix the reference by the local name of the API in config. Like that:

```
Check status of the server through Client API: `Client-API: GET /service/healthcheck`
Do the same through Admin API: `Admin-API: GET /service/healthcheck`
```

Here `Client-API: ` and `Admin-API: ` are prefixes. And they should be the same as your API names in the config.

Now each reference will be replaced with the link to corresponding API web-page.

***

apilinks is a highly customizable preprocessor. You can tune:

- the format of the references;
- the output string which will replace the reference;
- the format of the headings in your API web-page;
- and more!

For details look through the following sections.

Glossary:

- **reference** — reference to an API method in the source file. The one to be replaced with the link, e.g. `GET user/config`
- **verb** — HTTP method, e.g. `GET`, `POST`, etc.
- **command** — resource used to represent method on the API documentation webpage, e.g. `/service/healthcheck`.
- **endpoint prefix** — A prefix from server root to the command. If the command is `/user/status` and full resource is `/api/v0/user/satus` then the endpoint-prefix should be stated `/api/v0`. In references you can use either full resource (`{endpoint_prefix}/{command}`) or just the command. apilinks will sort it out for you.
- **output** — string, which will replace the *reference*.
- **header** — HTML header on the API documentation web-page of the method description, e.g. `<h2 id="get-user-config">GET user/config</h2>`
- **anchor** — web-anchor leading to the specific *header* on the API documentation web-page, e.g. `#get-user-config`

## How Does It Work?

Preprocessor can work in *online* and *offline* modes.

**In offline mode** it merely replaces *references* to API methods with links to their description. The references are catched by a regular expression. The link url is taken from config and the link *anchor* is generated from the reference automatically.

You can have several different APIs stated in the config. You can use prefixes to point out which API is being *reference*d. Prefixes format may be customized  in the configuration but by default you do it like this: `Client-API: GET user/name`. Here '*Client-API*' is a prefix.

If you don't use prefix in the *reference* preprocessor will suppose that you meant the default API, which is marked by `default` option in config. If none of them is marked — goes for the first in list.

> Note, that Swagger UI API websites won't work in offline mode at all, because we need to download the spec file (swagger.json) to figure out the proper anchor to a method description.

**In online mode** things are getting interesting. Preprocessor actually goes to each of the API web-pages, and collects all method **headers**. Then it goes through your document's source: when it meets a *reference*, it looks through all the collected methods and replaces the reference with the correct link to it. If method is not found — preprocessor will show a warning and leave the reference unchanged. Same will happen if there are several methods with this name in different APIs.

Prefixes, explained before, are supported too.

## Config

To enable the preprocessor, add `apilinks` to `preprocessors` section in the project config:

```yaml
preprocessors:
  - apilinks
```

The preprocessor has a lot of options. For your convenience the required options are marked *(required)*; and those options which are used in customization are marked *(optional)*. Most likely you will need just one or two of the latter.

```yaml
preprocessors:
- apilinks:
    targets:
        - site
    offline: False
    trim_if_targets:
        - pdf
    prefix_to_ignore: Ignore
    reference:
        - regex: *ref_pattern
          only_with_prefixes: false
          only_defined_prefixes: true
          output_template: '[{verb} {command}]({url})'
          trim_template: '`{verb} {command}`'
    API:
        Client-API:
            url: http://example.com/api/client
            default: true
            header_template: '{verb} {command}'
            site_backend: slate
        Admin-API:
            url: http://example.com/api/client
            header_template: '{command}'
            endpoint-prefix: /api/v0
            site_backend: aglio
        Internal-API:
            url: http://example.com/swagger-ui
            spec: http://example.com/swagger-ui/swagger.json
            site_backend: swagger
```


`prefix_to_ignore`
:   *(optional)* A default prefix for ignoring references. If apilinks meets a reference with this prefix it leaves it unchanged. Default: `Ignore`

`targets`
:   *(optional)* List of supported targets for `foliant make` command. If target is not listed here — preprocessor won't be applied. If the list is empty — preprocessor will be applied for any target. Default: `[]`

`offline`
:   *(optional)* Option determining whether the preprocessor will work in *online* or *offline* mode. Details in the **How Does It Work?** and **Online and Offline Modes Comparison** sections. Default: `False`

`trim_if_targets`
:   *(optional)* List of targets for `foliant make` command for which the prefixes from all *references* in the text will be cut out. Default: `[]`

> Only those references whose prefixes are defined in the `API` section (described below) are affected by this option. All references with unlisted prefixes will not be trimmed.

`reference`
:   *(optional)* A subsection for listing all the types of references you are going to catch in the text, and their properties. Options for this section are listed below.

***

**Reference options**
`regex`
:   *(optional)* regular expression used to catch *references* in the source. Look for details in the **Capturing References** section.
Default:

```
(?P<source>`((?P<prefix>[\w-]+):\s*)?(?P<verb>OPTIONS|GET|HEAD|POST|PUT|DELETE|TRACE|CONNECT|PATCH|LINK|UNLINK)\s+(?P<command>\S+)`)
```

`only_with_prefixes`
:   *(optional)* if this is `true`, only *references* with prefix will be transformed. Ordinary links like `GET user/info` will be ignored. Default: `false`

`only_defined_prefixes`
:   *(optional)* if this is `true` all references whose prefix is not listed in the `API` section (described below) will be ignored, left unchanged. References without prefix are not affected by this option. Default: `false`.

`output_template`
:   *(optional)* A template string describing the *output* which will replace the *reference*. More info in the **Customizing Output** section. Default: `'[{verb} {command}]({url})'`

`trim_template`
:   *(optional)* Only for targets listed in `trim_if_targets` option. Tune this template if you want to customize how apilinks cuts out prefixes. The reference will be replaced with text based on this template. Default: ```'`{verb} {command}`'```

***

`API`
:   *(required)* A subsection for listing all the APIs and their properties. Under this section there should be a separate subsection for each API. The section name represents the API name and, at the same time, the *prefix* used in the references. You need to add at least one API subsection for preprocessor to work.

***

**API properties**

`url`
:   *(required)* An API documentation web-page URL. It will be used to construct the full link to the method. In online mode it will also be parsed by preprocessor for validation.

`spec`
:   *(required for `swagger` and `redoc` site backends)* URL or local path to OpenAPI specification file.

`default`
:   *(optional)* Only for offline mode. Marker to define the default API. If several APIs are marked default, preprocessor will choose the first of them. If none is marked default — the first API in the list will be chosen. The value of this item should be `true`.

`header_template`
:   *(optional)* A template string describing the format of the headings in the API documentation web-page. It is needed to parse method headings from the web-page. Details in **parsing API web-page** section. Default: `'{verb} {command}'`

`endpoint-prefix`
:   *(optional)* The endpoint prefix from the server root to API methods. If is stated — apilinks can divide the command in the reference and search for it more accurately. Also you could use it in templates. More info coming soon. Default: `''`

`site_backend`
:   *(optional)* Name of the static site generator, which built your API documentation website. This affects how headers are converted to anchors. Default: `slate`. Available options: `aglio`, `mkdocs`, `redoc`, `slate`, `swagger`.

> If your API documentation website is built by another static site generator, there's still a chance that you will make it work with APILinks, because many of them use similar patterns to generate anchors. Just try one of  `aglio`, `mkdocs`, `slate` (but not `redoc` and `swagger`, these are special). If it doesn't work, send us a message, we will add support for your tool.

## Online and Offline Modes Comparison

> Note, that Swagger and Redoc sites won't work in offline mode

Let's study an example and look how the behavior of the preprocessor will change in online and offline modes.

We have three APIs described in the config:

```yaml
preprocessors:
  - apilinks:
      API:
        Admin-API:
            url: http://example.com/api/client
        Client-API:
            url: http://example.com/api/client
            default: true
            header_template: '{verb} {command}'
        Remote-API:
            url: https://remote.net/api-ref/
            header_template: '{command}'
```

Now let's look at different examples of the text used in Markdown source and how it is going to be transformed in Offline and Online modes

**Example 1**
Source:

```
Unprefixed link which only exists in Remote API: `GET system/info`.
```

In *Offline mode* preprocessor won't do any checks and just replace the reference with the link to default API from the config:

```
Unprefixed link which only exists in Remote API: [GET system/info](http://example.com/api/client/#get-system-info).
```

This is certainly a wrong decision, but it is our fault, we sould have added the prefix to the reference.

But let's look what will happen in *Online mode*:

```
Unprefixed link which only exists in Remote API: [GET system/info](https://remote.net/api-ref/#system-info).
```

Without any prefix the preprocessor determined that it should choose the Remote API to replace this reference because this method exists only on its page. The `default` option is just ignored in this mode.

By the way, notice how anchors differ in the two examples. For Remote API preprocessor used its header template to reconstruct the anchor, dropping the verb from it.

**Example 2**
Source:

```
Unprefixed link with misprint: `GET user/sttus`.
The link is incorrect, there's no such method in any of the APIs.
```

In *Offline mode* preprocessor won't do any checks again. No magic, the reference will be replaced with the link to default API from the config:

```
Unprefixed link with misprint: [GET user/sttus](http://example.com/api/client/#get-user-sttus).
The link is incorrect, there's no such method in any of the APIs.
```

In *Online mode* preprocessor won't be able to find the method during validation and the reference won't be replaced at all:

```
Unprefixed link with misprint: `GET user/sttus`.
The link is incorrect, there's no such method in any of the APIs.
```

During the Foliant project assembly you will see a warning message:

```
WARNING: Cannot find method GET user/sttus. Skipping
```

**Example 3**
Source:

```
Prefixed link to the Admin API: `Admin-API: POST user/ban_forever`.
```

In *Offline mode* preprocessor will notice the prefix and will be able to replace the reference with an appropriate link:

```
Prefixed link to the Admin API: [POST user/ban_forever](http://example.com/api/client/#post-user-ban_forever).
```

Notice that prefix disappeared from the text. If you wish it to stay there — edit the `output_template` option to something like this: `'{prefix}: {verb} {command}'`.

In *Online mode* the result will be exactly the same. Preprocessor will check the Admin-API methods, find there the referenced method and replace it in the text:

```
Prefixed link to the Admin API: [POST user/ban_forever](http://example.com/api/client/#post-user-ban_forever).
```

**Example 4**

```
Prefixed link to the Remote API with a misprint: `Remote-API: GET billling/info`.
Oh no, the method is incorrect again.
```

In *Offline mode* preprocessor will perform no checks and just replace the reference with the link to Remote API:

```
Prefixed link to the Remote API with a misprint: [GET billling/info](https://remote.net/api-ref/#get-billling-info).
Oh no, the method is incorrect again.
```

*Online mode*, on the other hand, will make its homework. It will check whether the Remote API actually has the method *GET billling/info*. Finding out that it hasn't it will leave the reference unchanged:

```
Prefixed link to the Remote API with a misprint: `Remote-API: GET billling/info`.
Oh no, the method is incorrect again.
```

...and warn us with the message:

```
WARNING: Cannot find method GET billling/info in Remote-API. Skipping
```

**Example 5**

```
Now let's reference a method which is present in both Client and Admin APIs: `GET service/healthcheck`.
```

In *Offline mode* preprocessor will just replace the reference with a link to default API:

```
Now let's reference a method which is present in both Client and Admin APIs: [GET service/healthcheck](http://example.com/api/client/#get-service-healthcheck).
```

But in *Online mode* preprocessor will go through all API method lists. It will find several mentions of this exact method and, confused, won't replace the reference at all:

```
Now let's reference a method which is present in both Client and Admin APIs: `GET service/healthcheck`.
```

You will also see a warning:

```
WARNING: GET /service/healthcheck is present in several APIs (Admin-API, Client-API). Please, use prefix. Skipping
```

## Capturing References

APILinks uses regular expressions to capture *references* to API methods in Markdown files.

The default reg-ex is as following:

```re
(?P<source>`((?P<prefix>[\w-]+):\s*)?(?P<verb>OPTIONS|GET|HEAD|POST|PUT|DELETE|TRACE|CONNECT|PATCH|LINK|UNLINK)\s+(?P<command>\S+)`)
```

This expression accepts references like these:

- `Client-API: GET user/info`
- `UPDATE user/details`

> Notice that default expression uses *Named Capturing Groups*. You would probably want to use all of them too if you are to redefine the expression. Though not all of them are required, see the table below.

Group | Required | Description
----- | -------- | -----------
source | YES | The full original reference string
prefix | NO | Prefix pointing to the name of the API from config
verb | NO | HTTP verb as `GET`, `POST`, etc
command | YES | the full method resource as it is stated in the API header (may include endpoint prefix)

To redefine the regular expression add an option `reg-regex` to the preprocessor config.

For example, if you want to capture ONLY references with prefixes you may use the following:

```yaml
preprocessors:
  - apilinks:
      reference:
      - regex: '(?P<source>`((?P<prefix>[\w-]+):\s*)(?P<verb>POST|GET|PUT|UPDATE|DELETE)\s+(?P<command>\S+)`)'
```

> This example is for illustrative purposes only. You can achieve the same goal by just switching on the `only_with_prefixes` option.

Now the references without prefix (`UPDATE user/details`) will be ignored.

## Customizing Output

You can customize the *output*-string which will replace the *reference* string. To do that add a template into your config-file.

A *template* is a string which may contain properties, surrounded by curly braces. These properties will be replaced with the values, and all the rest will remain unchanged.

For example, look at the default template:

```yaml
preprocessors:
  - apilinks:
    reference:
      - output_template: '[{verb} {command}]({url})',
```

> Don't forget the single quotes around the template. This way we say to yaml engine that this is a string for it not to be confused with curly braces.

With the default template, the reference string will be replaced by something like that:

```
[GET user/info](http://example.com/api/#get-user-info)
```

If you don't want references to be transfromed into links, use your own template. Properties you may use in the template:

property | description | example
-------- | ----------- | -------
url | Full url to the method description | `http://example.com/api/#get-user-info`
source | Full original reference string | \``Client-API: GET user/info`\`
prefix | Prefix used in the reference | `Client-API`
verb | HTTP verb used in the reference | `GET`
command | API command being referenced with endpoint prefix removed | `user/info`
endpoint_prefix | Endpoint prefix to the API (if `endpoint-prefix` option is filled in) | `/api/v0`

## Parsing API Web-page

**`aglio`, `mkdocs`, `slate` site backends**

In online mode APILinks goes through the API web-page content and gathers all the methods which are described there.

To do this preprocessor scans each HTML `h1`, `h2`, `h3`, `h4` tag and stores its `id` attribute (which is an *anchor* of the link to be constructed) and the contents of the tag (the *heading* itself).

For example in this link:

```html
<h2 id="get-user-info">GET user/info</h2>
```

the anchor would be `get-user-info` and the heading would be `GET user/info`.

To construct the link to the method description we will have to create the correct anchor for it. To create an anchor we would need to reconstruct the heading first. But the heading format may be arbitrary and that's why we need the `header_template` config option.

The `header_template` is a string which may contain properties, surrounded by curly braces. These properties will be replaced with the values, when preprocessor will attempt to reconstruct the heading. All the rest will remain unchanged.

For example, if your API headings look like this:

```
<h2 id="method-user-info-get">Method user/info (GET)</h2>
```

You should use the following option:

```yaml
...
API:
    Client-API:
        header_template: 'Method {command} ({verb})'
...
```

> Don't forget the single quotes around the template. This way we say to yaml engine that this is a string.

If your headers do not have a verb at all:

```
<h2 id="user-info">user/info</h2>
```

You should use the following option:

```yaml
...
API:
    Client-API:
        header_template: '{command}'
...
```

Properties you may use in the template:

property | description | example
-------- | ----------- | -------
verb | HTTP verb used in the reference | `GET`
command | API command being referenced | `user/info`
endpoint_prefix | Endpoint prefix to the API (if `endpoint-prefix` option is filled in) | `/api/v0`

**`swagger` and `redoc` site backends**

For Swagger and Redoc it's a bit different. To figure our the proper anchor to the method's description we need to know `operation_id` of the method. To get that we need the spec file (`swagger.json`) which was used to generate the website.

That's why for Swagger and Redoc sites APILinks parses not the website itself, but the specification file. Right now you can't customize the anchor format, it will be like this for Swagger:

```
#\{tag}\{operationId}
```

and like this for Redoc:

```
operation\{operationId}
```
