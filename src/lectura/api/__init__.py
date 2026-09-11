"""HTTP API.

The FastAPI instance lives in `server`, not `app`: exporting a name `app` from a
package that also contains a module `app` shadows the module, so
`import lectura.api.app` silently returned the FastAPI object instead.
"""

from lectura.api.server import app

__all__ = ["app"]
