//! r8 scorer selftest: answers 401 to every request. Not a port; it only shows
//! the scorer's pipeline (build, test, start, hidden tests) runs end to end.
use std::io::{Read, Write};
use std::net::TcpListener;

fn response() -> &'static [u8] {
    b"HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm=\"stub\"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
}

fn main() {
    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".into());
    let listener = TcpListener::bind(format!("0.0.0.0:{port}")).expect("bind");
    for stream in listener.incoming().flatten() {
        let mut stream = stream;
        let mut buf = [0u8; 8192];
        let _ = stream.read(&mut buf);
        let _ = stream.write_all(response());
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn answers_401() {
        assert!(super::response().starts_with(b"HTTP/1.1 401"));
    }
}
