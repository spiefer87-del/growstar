# Spider Farmer bridge certificate material

Growstar SF.1 contains the device-facing TLS certificate, matching private key,
and upstream CA certificate required for compatibility with Spider Farmer GGS
controllers.

These three PEM files are sourced from:

- Project: `cobragt2000/spider_farmer_bridge`
- Reference commit: `b95f50edd6fff3fbc74e0853e68490f1698ffa31`
- Paths:
  - `custom_components/sf/certs/server.pem`
  - `custom_components/sf/certs/server_key.pem`
  - `custom_components/sf/upstream_ca/upstream_ca.pem`

The source project publishes these files under the MIT License:

MIT License

Copyright (c) 2026 cobragt2000

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished
to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Security note: the private key is already public in the upstream repository and
is not a Growstar secret. The real trust boundary is who can redirect/reach the
GGS controller's traffic on the local network. Never expose the bridge listener
to the public internet.
