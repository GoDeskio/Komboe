# Server container (#93)

The server Dockerfile uses a Rust build stage and a Debian slim runtime stage. Only the compiled binary crosses the boundary. The runtime has a fixed unprivileged UID/GID, a mode-0700 data directory, port 8080, an exec-form entrypoint, and an `/alive` health check with start period and retry limits.

BuildKit caches Cargo downloads and target artifacts without embedding them in the image. A Dockerfile-specific ignore list limits the context to the server manifests, macros, migrations, and source, excluding the existing multi-gigabyte target directory. The web vault remains an explicit `/web-vault` mount. Container builds require network access to the locked Rust dependencies; environments without Docker should validate the Dockerfile statically and retain feature status as partial.
