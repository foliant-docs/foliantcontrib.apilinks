# apilinks Preprocessor for Foliant

Preprocessor for replacing API *reference*s in markdown files with links to actual method description on the API dcumentation web-page.

Glossary:

- **reference** — reference to an API method in the source file. This one will be replaced with the link.
- **verb** — HTTP method, e.g. `GET`, `POST`, etc.
- **command** — the endpoint used to represent method on the API documentation webpage, e.g. `service/healthcheck`.
- **output** — string, which will replace the *reference*.
- **header** — HTML header on the API documentation web-page of the method description. (now supporting only `h2` headers).
- **anchor** — web-anchor leading to the specific *header* on the API documentation web-page.

## How Does It Work?

Preprocessor can work in *online* and *offline* modes.

**In offline mode** it merely replaces *references* to API methods in the text by links based on the the URL to the API web-page from config and the *anchor* generated from the *reference*.

You can have several different APIs stated in the config. You can use prefixes to point out which API is being *reference*d. Prefixes format may be customized  in the configuration but by default you can do it like this: `Client-API: GET user/name`. Here '*Client-API*' is a prefix.

If you don't use prefix in the *reference* (and the regular expression which captures *reference*s allows that) preprocessor would suppose that you meant the default API, which is marked by `default` option in config or just the first one in the list (if none of them is marked).

**In online mode** things are getting interesting. Preprocessor actually goes to each of the API documentation web-pages, stated in the config and collects all method **headers** (right now only `h2` headers are supported). When it meets a *reference* to an API method, it looks through all the collected methods and replaces the reference with the correct link to it. If method is not found — preprocessor will show warning and leave the reference unchanged. Same will happen if there are methods with this name in several different APIs.

Prefixes, explained before, are supported too.

## Quick Start

Say, you have an API documentation hosted at the url http://example.com/api-docs

On this page you have HTML headings before each method description like this:

```html
<h2 id="get-user-authenticate">GET user/authenticate</h2>
```

And you want references these methods in your documentation to be replaced with the links to the actual method descriptions. Your references look like this:

```
To authenticate user use API method `GET user/authenticate`.
```

All you need to di is add the apilinks preprocessor into your foliant.yml and state your API url in its options like this:

```yaml
preprocessors:
    - apilinks:
        API:
            My-API:
                url: http://example.com/api-docs
```

Here:
- `API` is a required section for you to store your API properties;
- `My-API` is a local name of your API. Right now it is not very important but will come in handy in further examples;
- `url` is a string with full url to your API web-page documentation. It will be used to validate references and to replace them with a full URL to method doc.

After foliant applies the preprocessor your document will be transformed into this:

```
To authenticate user use API method [GET user/authenticate](http://example.com/api-docs/#get-user-authenticate).
```

Notice that preprocessor figured out the correct anchor `#get-user-authenticate` by himself. Now instead of plain name of the method you've got a link to the method description!

Ok, what if I have two different API docs webpages, say with client API and admin API. How can I reference to them in the same document?

No problem, put both of them into your config:

```yaml
preprocessors:
    - apilinks:
        API:
            Client-API:
                url: http://example.com/client/api-docs
            Admin-API:
                url: http://example.com/admin/api-docs
```

Now this source:

```
To authenticate user use API method `GET user/authenticate`.
To ban user from the website use admin API method `POST admin/ban_user/{user_id}`
```

Will be transformed by apilinks into this:

```
To authenticate user use API method [GET user/authenticate](http://example.com/client/api-docs/#get-user-authenticate).
To ban user from the website use admin API method [POST admin/ban_user/{user_id}](http://example.com/admin/api-docs/#post-admin-ban_user-user_id)
```

Notice that apilinks determined that the first reference is from Client API, and the second one is from the Admin API. How is that possible? Easy: preprocessor parses each API url from the config and stores their methods. When it processes the reference it looks for the referenced method in each stored list and determines which API is being referenced.

But what if we have the same-named method in both of our APIs? In this case you will see a warning:

```
WARNING: GET /service/healthcheck is present in several APIs (Client-API, Admin-API). Please, use prefix. Skipping
```

It says us to use prefix, and by that it means to prefix the reference by the local name of the API in config. Like that:

```
Check status of the server through Client API: `Client-API: GET /service/healthcheck`
Do the same through Admin API: `Admin-API: GET /service/healthcheck`
```

Now each reference will be replaced with the link to corresponding API web-page.

apilinks is a highly customizable preprocessor. You can tune:

- the format of the references;
- the output string which will replace the reference;
- the format of the headings in your API web-page;
- and more!

For details look through the following sections.

## Installation

```shell
$ pip install foliantcontrib.apilinks
```

## Config

To enable the preprocessor, add `apilinks` to `preprocessors` section in the project config:

```yaml
preprocessors:
  - apilinks
```

The preprocessor has a lot of options. For your convenience those options which are not required (in other words are used in customization) are marked *(optional)*. Options which you should definitely understand are marked as *(required)*.

```yaml
preprocessors:
  - apilinks:
      ref-regex: *ref_pattern
      output-template: '[{verb} {command}]({url})',
      targets:
        - site
      offline: False
      API:
        Client-API:
            url: http://example.com/api/client
            default: true
            header-template: '{verb} {command}'
        Admin-API:
            url: http://example.com/api/client
            header-template: '{command}'
```

`ref-regex`
:   *(optional)* regular expression to catch references in the source. Details in the **capturing references** section. Default: '(?P<source>\`((?P<prefix>[\w-]+):\s*)?(?P<verb>POST|GET|PUT|UPDATE|DELETE)\s+(?P<command>\S+)\`)'

`output-template`
:   *(optional)* A template string describing the *output* which will replace the *reference*. Details in the **customizing output** section. Default: `'[{verb} {command}]({url})'`

`targets`
:   *(optional)* List of supported targets for `foliant make` command. If target is not listed here — preprocessor won't be applied. If the list is empty — will be applied to any target. Default: `[]`

`offline`
:   *(optional)* Option determining whether the preprocessor will work in *online* or *offline* mode. Details in the **How does it work?** section. Default: `False`

`API`
:   *(required)* A subsection for listing all the APIs, references to whose methods you want to replace. Its value is a dictionary where each key represents an API name and the value — the API properties. You need to add at least one API to this section for preprocessor to work. Default: `{}`

**API properties**

`url`
:   *(required)* An API documentation web-page URL. In online mode it will be parsed by preprocessor.

`default`
:   *(optional)* Only for offline mode. Marker to define the default API. If several APIs are marked default, preprocessor would choose the first of them. If none is marked default — the first API in the list will be chosen.

`header-template`
:   *(optional)* A template string describing the format of the headings in the API documentation web-page. Details in **parsing API web-page** section. Default: '{verb} {command}'

## Capturing References

apilinks uses regular expressions to capture *references* to API methods.

The default reg-ex is as following:

```re
(?P<source>`((?P<prefix>[\w-]+):\s*)?(?P<verb>POST|GET|PUT|UPDATE|DELETE)\s+(?P<command>\S+)`)
```

This expression accepts these kinds of references:

- `Client-API: GET user/info`
- `UPDATE user/details`

Notice that default expression uses Named Capturing Groups. You would probably want to use all of them too if you are to redefine the expression. But not all are required. Details in the table below.

Group | Required | Description
----- | -------- | -----------
source | YES | The full original reference string
prefix | NO | Prefix pointing to the name of the API to use from config
verb | NO | HTTP verb as `GET`, `POST, etc
command | YES | the full method resource name as it is stated in API header

To redefine the regular expression used to capture references add an option `reg-regex` to the preprocessor options.

For example, if you want to capture ONLY references with prefixes you may use the following:

```yaml
preprocessors:
  - apilinks:
      ref-regex: '(?P<source>`((?P<prefix>[\w-]+):\s*)(?P<verb>POST|GET|PUT|UPDATE|DELETE)\s+(?P<command>\S+)`)'
```

Don't forget the single quotes around a regular expression. This way we say to yaml processor that this is a string.

Now the references without prefix (`UPDATE user/details`) will be ignored.

## Customizing Output

You can customize the *output*-string which will replace the *reference* string. To do that add a template into your config-file.

A *template* is a string which may contain properties, surrounded by curly braces. These properties will be replaced with the values, all the rest remaining unchanged.

For example, if we use the default template:

```yaml
preprocessors:
  - apilinks:
      output-template: '[{verb} {command}]({url})',
```

Don't forget the single quotes around the template. This way we say to yaml processor that this is a string for it not to be confused with curly braces.

The reference string will be replaced by something like that:

```
[GET user/info](http://example.com/api/#get-user-info)
```

Properties you may use in the template:

property | description | example
-------- | ----------- | -------
url | Full url to the method description | `http://example.com/api/#get-user-info`
source | Full original reference string | \``Client-API: GET user/info`\`
prefix | Prefix used in the reference | `Client-API`
verb | HTTP verb used in the reference | `GET`
command | API command being referenced | `user/info`

## Parsing API Web-page

apilinks goes through the API web-page content and gathers all the methods which are described there.

To do this preprocessor scans each HTML `h2` tag and stores its `id` attribute (which is an anchor of the link to be constructed) and the contents of the tag (the heading itself).

For example in this link

```html
<h2 id="get-user-info">GET user/info</h2>
```

the anchor would be `get-user-info`; the heading would be `GET user/info`.

To construct the correct link to the method description we will have to create the correct anchor for it. To create an anchor we would need to reconstruct the heading first. But the heading format may be arbitrary and that's why we need the `header-template` config option.

The `header-template` is a string which may contain properties, surrounded by curly braces. These properties will be replaced with the values, when preprocessor will attempt to reconstruct the heading. All the rest symbols will remain unchanged.

Properties you may use in the template:

property | description | example
-------- | ----------- | -------
verb | HTTP verb used in the reference | `GET`
command | API command being referenced | `user/info`

For example, if your API headings look like this:

```
Method user/info (GET)
```

You should use the following option:

```yaml
...
API:
    Client-API:
        header-template: 'Method {command} ({verb})'
...
```

Don't forget the single quotes around the template. This way we say to yaml processor that this is a string for it not to be confused with curly braces.

If your headers do not have verb at all:

```
Method user/info (GET)
```

You should use the following option:

```yaml
...
API:
    Client-API:
        header-template: '{command}'
...
```

