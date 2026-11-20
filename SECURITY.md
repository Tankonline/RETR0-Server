# Security policy

## Scope

The RETR0 server is designed to run **only on `127.0.0.1`** for a single player. It is not hardened for exposure to
a network or the internet. Please report:

- anything that makes a service listen on, or be reachable from, a non-loopback address unexpectedly;
- path traversal or file access outside the server folder (e.g. via the cloud-save or file endpoints);
- crashes or hangs triggered by malformed requests;
- anything that would make the server or the client contact a third party.

## Reporting

Please **do not open a public issue** for a vulnerability. Use GitHub's **private vulnerability reporting**
("Security" tab → "Report a vulnerability") on this repository. Include steps to reproduce and the affected file.

## Not in scope

- The game client itself, EA services, or third-party SDKs bundled with the game.
- Running the server deliberately on a public interface.
