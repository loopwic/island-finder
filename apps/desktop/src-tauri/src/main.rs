use std::{
    env,
    io::{self, Write},
    net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};

use tauri::{Manager, RunEvent, WindowEvent};

const CONTROLLER_PORT: u16 = 32_145;
const VISION_PORT: u16 = 48_197;

#[derive(Clone, Default)]
struct RuntimeProcess {
    inner: Arc<RuntimeProcessInner>,
}

#[derive(Default)]
struct RuntimeProcessInner {
    child: Mutex<Option<Child>>,
    stopping: AtomicBool,
}

impl RuntimeProcess {
    fn install(&self, child: Child) {
        *self
            .inner
            .child
            .lock()
            .expect("runtime child lock poisoned") = Some(child);
    }

    fn monitor(&self, app: tauri::AppHandle) {
        let runtime = self.clone();
        thread::spawn(move || {
            loop {
                thread::sleep(Duration::from_millis(250));
                let exit_status = {
                    let mut guard = runtime
                        .inner
                        .child
                        .lock()
                        .expect("runtime child lock poisoned");
                    let Some(child) = guard.as_mut() else {
                        return;
                    };
                    match child.try_wait() {
                        Ok(Some(status)) => {
                            guard.take();
                            Some(status)
                        }
                        Ok(None) => None,
                        Err(error) => {
                            eprintln!("无法读取 Island Finder 运行时状态：{error}");
                            guard.take();
                            return app.exit(1);
                        }
                    }
                };
                if let Some(status) = exit_status {
                    if !runtime.inner.stopping.load(Ordering::SeqCst) {
                        if status.success() {
                            println!("Island Finder 运行时已由外部安全停止。退出桌面应用。")
                        } else {
                            eprintln!("Island Finder 运行时意外退出：{status}");
                        }
                        app.exit(status.code().unwrap_or(1));
                    }
                    return;
                }
            }
        });
    }

    fn shutdown(&self) {
        if self.inner.stopping.swap(true, Ordering::SeqCst) {
            return;
        }
        let child = self
            .inner
            .child
            .lock()
            .expect("runtime child lock poisoned")
            .take();
        let Some(mut child) = child else {
            return;
        };
        if let Some(mut stdin) = child.stdin.take() {
            let _ = stdin.write_all(b"shutdown\n");
            let _ = stdin.flush();
        }
        let deadline = Instant::now() + Duration::from_secs(8);
        while Instant::now() < deadline {
            match child.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) => thread::sleep(Duration::from_millis(100)),
                Err(_) => break,
            }
        }
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn project_root() -> io::Result<PathBuf> {
    if let Some(value) = env::var_os("ISLAND_FINDER_PROJECT_ROOT") {
        return PathBuf::from(value).canonicalize();
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
}

fn port_is_open(port: u16) -> bool {
    TcpStream::connect_timeout(
        &SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port),
        Duration::from_millis(200),
    )
    .is_ok()
}

fn wait_until_ready(child: &mut Child, timeout: Duration) -> io::Result<()> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if let Some(status) = child.try_wait()? {
            return Err(io::Error::other(format!(
                "Island Finder 运行时在就绪前退出：{status}"
            )));
        }
        if port_is_open(CONTROLLER_PORT) && port_is_open(VISION_PORT) {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err(io::Error::new(
        io::ErrorKind::TimedOut,
        "Island Finder 运行时在 35 秒内没有就绪",
    ))
}

fn spawn_runtime() -> io::Result<Child> {
    let root = project_root()?;
    let supervisor = root.join("vision_service/runtime_supervisor.py");
    let uv = env::var_os("ISLAND_FINDER_UV_BIN").unwrap_or_else(|| "uv".into());
    let mut command = Command::new(uv);
    command
        .current_dir(&root)
        .arg("run")
        .arg("--project")
        .arg(&root)
        .arg("--frozen")
        .arg("python")
        .arg(supervisor)
        .arg("--parent-pid")
        .arg(std::process::id().to_string())
        .arg("--watch-stdin")
        .stdin(Stdio::piped())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());
    let mut child = command.spawn()?;
    if let Err(error) = wait_until_ready(&mut child, Duration::from_secs(35)) {
        let _ = child.kill();
        let _ = child.wait();
        return Err(error);
    }
    Ok(child)
}

fn main() {
    let runtime = RuntimeProcess::default();
    let app = tauri::Builder::default()
        .manage(runtime.clone())
        .setup(move |app| {
            let child = spawn_runtime()?;
            runtime.install(child);
            runtime.monitor(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("无法创建 Island Finder 桌面应用");

    app.run(|app, event| match event {
        RunEvent::WindowEvent {
            event: WindowEvent::CloseRequested { .. },
            ..
        } => {
            app.state::<RuntimeProcess>().shutdown();
            app.exit(0);
        }
        RunEvent::ExitRequested { .. } | RunEvent::Exit => {
            app.state::<RuntimeProcess>().shutdown();
        }
        _ => {}
    });
}
