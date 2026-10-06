use std::{env, fs, process};
fn main() {
    let args: Vec<_> = env::args().collect();
    if args.len() != 2 {
        process::exit(64);
    }
    let bytes = fs::read(&args[1]).unwrap_or_else(|_| process::exit(65));
    let result = sage_einsums::protocol::execute(&bytes).unwrap_or_else(|_| process::exit(65));
    println!("{}", sage_einsums::protocol::json(&result));
}
