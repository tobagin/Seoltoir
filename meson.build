project(
  'io.github.tobagin.seoltoir', # Simplified project ID
  'c', # Dummy language as we're treating Python as an external program
  version: '0.1.0',
  meson_version: '>= 0.60.0',
  default_options: [
    'prefix=/usr',
    'libdir=lib',
  ],
)

python3_exe = find_program('python3', required: true)

# --- Dependencies ---
gtk4_dep = dependency('gtk4', version: '>= 4.18')
adwaita_dep = dependency('libadwaita-1', version: '>= 1.7')
webkitgtk_dep = dependency('webkitgtk-6.0', version: '>= 2.48')

# Get the Python installation's site-packages (purelib) directory reliably.
python_version_result = run_command(python3_exe, '-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")', check: true)
python_version = python_version_result.stdout().strip()
python_site_packages_dir = join_paths(get_option('prefix'), 'lib', 'python' + python_version, 'site-packages')


# --- Application Installation ---
# Install the Python source files directly into site-packages/seoltoir
# This assumes the 'src/seoltoir' folder contains the Python package.
install_data(
  [
    'src/seoltoir/__init__.py',
    'src/seoltoir/main.py',
    'src/seoltoir/window.py',
    'src/seoltoir/adblock_parser.py',
    'src/seoltoir/database.py',
    'src/seoltoir/history_manager.py',
    'src/seoltoir/download_manager.py',
    'src/seoltoir/preferences_window.py',
    'src/seoltoir/clear_data_dialog.py',
    'src/seoltoir/search_engine_dialog.py',
    'src/seoltoir/https_everywhere_rules.py',
    'src/seoltoir/site_settings_dialog.py',
    'src/seoltoir/browser_view.py',
    'src/seoltoir/bookmark_manager.py',
    'src/seoltoir/import_export_dialog.py',
    'src/seoltoir/container_manager.py',
    'src/seoltoir/search_engine_manager.py',
    'src/seoltoir/opensearch_parser.py',
    'src/seoltoir/search_suggestions_client.py',
    'src/seoltoir/ui_loader.py',
    'src/seoltoir/debug.py',
    'src/seoltoir/password_manager.py',
    'src/seoltoir/password_manager_window.py',
    'src/seoltoir/password_import_export.py',
    'src/seoltoir/pip_window.py',
    'src/seoltoir/performance_manager.py',
    'src/seoltoir/performance_monitor.py',
    'src/seoltoir/omnibox_entry.py',
    'src/seoltoir/reader_mode.js',
    'src/seoltoir/reader_mode.css',
    'src/seoltoir/reader_mode_preferences.py',
  ],
  install_dir: join_paths(python_site_packages_dir, 'seoltoir'),
)

# --- Data Files Installation ---
data_dir = get_option('datadir')

# UI files
install_data(
  [
    'data/ui/main-window.ui',
    'data/ui/main-content.ui',
    'data/ui/menu.ui',
    'data/ui/preferences-window.ui',
    'data/ui/search-engine-dialog.ui',
    'data/ui/clear-data-dialog.ui',
    'data/ui/import-export-dialog.ui',
    'data/ui/site-settings-dialog.ui',
    'data/ui/history-manager.ui',
    'data/ui/bookmark-manager.ui',
    'data/ui/download-manager.ui',
    'data/ui/reader-mode-preferences.ui',
  ],
  install_dir: data_dir / 'seoltoir' / 'ui',
)

# Desktop file for application launcher
install_data(
  'data/io.github.tobagin.seoltoir.desktop',
  install_dir: data_dir / 'applications',
)

# AppStream metadata for software centers
install_data(
  'data/io.github.tobagin.seoltoir.appdata.xml',
  install_dir: data_dir / 'metainfo',
)

# GSettings schema for application preferences
install_data(
  'data/io.github.tobagin.seoltoir.gschema.xml',
  install_dir: data_dir / 'glib-2.0' / 'schemas',
)

# Icons
install_data(
  'data/icons/hicolor/256x256/apps/io.github.tobagin.seoltoir.png',
  install_dir: data_dir / 'icons' / 'hicolor' / '256x256' / 'apps',
)
install_data(
  'data/icons/hicolor/64x64/apps/io.github.tobagin.seoltoir.png',
  install_dir: data_dir / 'icons' / 'hicolor' / '64x64' / 'apps',
)
install_data(
  'data/icons/hicolor/48x48/apps/io.github.tobagin.seoltoir.png',
  install_dir: data_dir / 'icons' / 'hicolor' / '48x48' / 'apps',
)
install_data(
  'data/icons/hicolor/32x32/apps/io.github.tobagin.seoltoir.png',
  install_dir: data_dir / 'icons' / 'hicolor' / '32x32' / 'apps',
)
install_data(
  'data/icons/hicolor/24x24/apps/io.github.tobagin.seoltoir.png',
  install_dir: data_dir / 'icons' / 'hicolor' / '24x24' / 'apps',
)
install_data(
  'data/icons/hicolor/16x16/apps/io.github.tobagin.seoltoir.png',
  install_dir: data_dir / 'icons' / 'hicolor' / '16x16' / 'apps',
)
install_data(
  'data/icons/hicolor/512x512/apps/io.github.tobagin.seoltoir.png',
  install_dir: data_dir / 'icons' / 'hicolor' / '512x512' / 'apps',
)

# Symbolic SVG icons for UI elements
install_data(
  'data/icons/hicolor/scalable/apps/io.github.tobagin.seoltoir-tab-add-symbolic.svg',
  install_dir: data_dir / 'icons' / 'hicolor' / 'scalable' / 'apps',
)
install_data(
  'data/icons/hicolor/scalable/apps/io.github.tobagin.seoltoir-tab-add-private-symbolic.svg',
  install_dir: data_dir / 'icons' / 'hicolor' / 'scalable' / 'apps',
)
install_data(
  'data/icons/hicolor/scalable/apps/io.github.tobagin.seoltoir-cookies-symbolic.svg',
  install_dir: data_dir / 'icons' / 'hicolor' / 'scalable' / 'apps',
)

# --- Executable Script ---
app_name = 'seoltoir'
configure_file(
  input: 'data/@0@.in'.format(app_name),
  output: app_name,
  install_dir: get_option('bindir'),
  install: true,
  configuration: {
    'PYTHON_EXECUTABLE': python3_exe.full_path(),
    'APP_ID': meson.project_name(), # Use simplified APP_ID
    'PYTHON_SITE_PACKAGES': python_site_packages_dir # Pass the calculated site-packages dir
  },
  install_mode: 'rwxr-xr-x'
)
