//! Writes the official content files (`content/*.json`) from the engine's
//! definitions: `cargo run -p sts-engine --example export_content`.

fn main() {
    let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../content");
    std::fs::create_dir_all(&dir).unwrap();
    for (name, text) in sts_engine::registry::official_files() {
        std::fs::write(dir.join(name), text).unwrap();
        println!("wrote content/{name}");
    }
}
