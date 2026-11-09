# Security policy

## Supported versions

Only the latest release receives security fixes while the project is below
version 1.0.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Report it privately through GitHub: go to the repository's **Security** tab
and choose **Report a vulnerability**. Include the version, how to reproduce
the problem, and what impact you expect.

You should get an acknowledgement within 7 days. Once the problem is
confirmed, a fix and an advisory will be published, and you will be credited
unless you prefer not to be.

## Scope

cronlens reads files from disk and prints reports. It makes no network
requests and needs no credentials. Relevant issues include, for example:

- crafted YAML or crontab input that causes code execution, excessive memory
  use or a hang;
- output (such as SARIF) that could inject content into the tools that
  display it;
- problems in the GitHub Action, such as command injection through its inputs.

YAML is always loaded with PyYAML's safe loader.
