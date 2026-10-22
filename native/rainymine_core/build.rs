fn main() {
    cc::Build::new().cpp(true).std("c++17").include("vendor/mineflow")
        .file("vendor/mineflow/mineflow.cpp").file("src/closure.cpp")
        .flag_if_supported("/EHsc").compile("rainymine_pseudoflow");
    println!("cargo:rerun-if-changed=src/closure.cpp");
    println!("cargo:rerun-if-changed=vendor/mineflow/mineflow.cpp");
}
