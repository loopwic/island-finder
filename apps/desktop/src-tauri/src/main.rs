use std::{
    env, fs,
    io::{self, Write},
    net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream},
    path::{Path, PathBuf},
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
const RUNTIME_RESTART_LIMIT: usize = 3;

#[derive(Clone)]
struct RuntimeLaunch {
    resource_dir: Option<PathBuf>,
    app_data_dir: Option<PathBuf>,
    app_cache_dir: Option<PathBuf>,
}

#[derive(Clone, Default)]
struct RuntimeProcess {
    inner: Arc<RuntimeProcessInner>,
}

#[derive(Default)]
struct RuntimeProcessInner {
    child: Mutex<Option<Child>>,
    launch: Mutex<Option<RuntimeLaunch>>,
    stopping: AtomicBool,
    monitor_started: AtomicBool,
    recovery_exhausted: AtomicBool,
}

impl RuntimeProcess {
    fn configure(&self, launch: RuntimeLaunch) {
        *self
            .inner
            .launch
            .lock()
            .expect("runtime launch lock poisoned") = Some(launch);
    }

    fn install(&self, child: Child) {
        *self
            .inner
            .child
            .lock()
            .expect("runtime child lock poisoned") = Some(child);
    }

    fn take_child(&self) -> Option<Child> {
        self.inner
            .child
            .lock()
            .expect("runtime child lock poisoned")
            .take()
    }

    fn stop_child(mut child: Child) {
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

    fn spawn_with_retries(&self) -> bool {
        let launch = self
            .inner
            .launch
            .lock()
            .expect("runtime launch lock poisoned")
            .clone();
        let Some(launch) = launch else {
            eprintln!("Island Finder 运行时缺少启动配置，无法恢复。");
            return false;
        };

        for attempt in 1..=RUNTIME_RESTART_LIMIT {
            if self.inner.stopping.load(Ordering::SeqCst) {
                return false;
            }
            if attempt > 1 {
                thread::sleep(Duration::from_secs((attempt - 1) as u64));
            }
            match spawn_runtime(&launch) {
                Ok(child) => {
                    if self.inner.stopping.load(Ordering::SeqCst) {
                        Self::stop_child(child);
                        return false;
                    }
                    self.install(child);
                    println!("Island Finder 运行时已在第 {attempt} 次尝试恢复。");
                    return true;
                }
                Err(error) => {
                    eprintln!(
                        "Island Finder 运行时第 {attempt}/{RUNTIME_RESTART_LIMIT} 次恢复失败：{error}"
                    );
                }
            }
        }
        eprintln!("Island Finder 运行时三轮恢复均失败，桌面窗口保持打开以便手动重试。");
        false
    }

    fn recover(&self) {
        let recovered = self.spawn_with_retries();
        self.inner
            .recovery_exhausted
            .store(!recovered, Ordering::SeqCst);
    }

    fn monitor(&self) {
        if self.inner.monitor_started.swap(true, Ordering::SeqCst) {
            return;
        }
        let runtime = self.clone();
        thread::spawn(move || {
            loop {
                thread::sleep(Duration::from_millis(250));
                if runtime.inner.stopping.load(Ordering::SeqCst) {
                    return;
                }
                let child_result = {
                    let mut guard = runtime
                        .inner
                        .child
                        .lock()
                        .expect("runtime child lock poisoned");
                    let Some(child) = guard.as_mut() else {
                        drop(guard);
                        if !runtime.inner.recovery_exhausted.load(Ordering::SeqCst) {
                            runtime.recover();
                        }
                        continue;
                    };
                    match child.try_wait() {
                        Ok(Some(status)) => {
                            guard.take();
                            Ok(Some(status))
                        }
                        Ok(None) => Ok(None),
                        Err(error) => {
                            guard.take();
                            Err(error)
                        }
                    }
                };
                match child_result {
                    Ok(Some(status)) => {
                        if !runtime.inner.stopping.load(Ordering::SeqCst) {
                            eprintln!("Island Finder 运行时已退出（{status}），开始安全恢复。");
                            runtime.recover();
                        }
                    }
                    Err(error) => {
                        eprintln!("无法读取 Island Finder 运行时状态：{error}；开始安全恢复。");
                        runtime.recover();
                    }
                    Ok(None) => {}
                }
            }
        });
    }

    fn shutdown(&self) {
        if self.inner.stopping.swap(true, Ordering::SeqCst) {
            return;
        }
        self.inner.recovery_exhausted.store(true, Ordering::SeqCst);
        let Some(child) = self.take_child() else {
            return;
        };
        Self::stop_child(child);
    }
}

fn find_project_root(start: &Path) -> Option<PathBuf> {
    start.ancestors().find_map(|candidate| {
        let supervisor = candidate.join("vision_service/runtime_supervisor.py");
        let project = candidate.join("pyproject.toml");
        if supervisor.is_file() && project.is_file() {
            candidate.canonicalize().ok()
        } else {
            None
        }
    })
}

fn project_root(resource_dir: Option<&Path>) -> io::Result<(PathBuf, bool)> {
    if let Some(value) = env::var_os("ISLAND_FINDER_PROJECT_ROOT") {
        return PathBuf::from(value)
            .canonicalize()
            .map(|root| (root, false));
    }
    if let Some(root) = resource_dir
        .map(|resources| resources.join("runtime"))
        .as_deref()
        .and_then(find_project_root)
    {
        return Ok((root, true));
    }
    if let Some(root) = env::current_exe()
        .ok()
        .and_then(|executable| executable.parent().and_then(find_project_root))
    {
        return Ok((root, false));
    }
    if let Some(root) = env::current_dir()
        .ok()
        .and_then(|cwd| find_project_root(&cwd))
    {
        return Ok((root, false));
    }
    Err(io::Error::new(
        io::ErrorKind::NotFound,
        "可执行文件旁未找到 Island Finder 运行资源；请保留完整的 Island-Finder 文件夹",
    ))
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

fn spawn_runtime(launch: &RuntimeLaunch) -> io::Result<Child> {
    let (root, bundled) = project_root(launch.resource_dir.as_deref())?;
    let supervisor = root.join("vision_service/runtime_supervisor.py");
    let bundled_uv = root
        .join("bin")
        .join(if cfg!(windows) { "uv.exe" } else { "uv" });
    let uv = env::var_os("ISLAND_FINDER_UV_BIN")
        .or_else(|| bundled_uv.is_file().then(|| bundled_uv.into_os_string()))
        .unwrap_or_else(|| "uv".into());
    let mut command = Command::new(uv);
    if bundled {
        let data_root = launch
            .app_data_dir
            .as_deref()
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "无法确定应用数据目录"))?;
        let cache_root = launch
            .app_cache_dir
            .as_deref()
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "无法确定应用缓存目录"))?;
        let settings_dir = data_root.join("data");
        let environment_dir = data_root.join("venv");
        let capture_build_dir = cache_root.join("native-capture");
        fs::create_dir_all(&settings_dir)?;
        fs::create_dir_all(&capture_build_dir)?;
        command
            .env("ISLAND_FINDER_DATA_DIR", settings_dir)
            .env("ISLAND_FINDER_BUILD_DIR", capture_build_dir)
            .env("UV_PROJECT_ENVIRONMENT", environment_dir)
            .env("PYTHONDONTWRITEBYTECODE", "1");
    }
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
            let launch = RuntimeLaunch {
                resource_dir: Some(app.path().resource_dir()?),
                app_data_dir: Some(app.path().app_data_dir()?),
                app_cache_dir: Some(app.path().app_cache_dir()?),
            };
            runtime.configure(launch);
            runtime.monitor();
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
