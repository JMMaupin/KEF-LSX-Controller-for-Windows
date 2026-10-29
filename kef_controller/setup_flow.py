"""What the executable does before it is the application: install,
update, uninstall.

Called from main.py before the single-instance lock is taken: the
downloaded copy must be able to replace an installed copy that is running.
"""

import logging

from . import elevation, installer, paths, product

log = logging.getLogger("kef_controller")


def handles(argv):
    """True if this launch is an installation or a removal."""
    return installer.INSTALL_ARGUMENT in argv or installer.UNINSTALL_ARGUMENT in argv


def should_offer(argv):
    """The executable started from anywhere but its installation folder --
    a download, a USB stick -- offers to install or update itself first.

    Not at boot: a Run entry pointing at a copy run without installing
    must start the application, not ask a question nobody is there to see.
    """
    return (paths.is_frozen() and not paths.running_installed_copy()
            and installer.STARTUP_ARGUMENT not in argv)


def offer(argv):
    """Ask what to do with a non-installed executable; None to just run it."""
    from . import setup_dialog

    choice = setup_dialog.ask_setup(installer.installed_version())
    if choice == "run":
        return None
    if choice == "open":
        installer.start_installed()
        return 0
    if choice == "install":
        return _install_from_launcher(silent=False)
    return 0


def run(argv):
    """`--install` and `--uninstall`, elevated or not yet."""
    from . import setup_dialog

    silent = installer.SILENT_ARGUMENT in argv
    spare = installer.parse_spare(argv)
    elevated = elevation.is_elevated()

    if installer.INSTALL_ARGUMENT in argv:
        if not elevated:
            return _install_from_launcher(silent=silent)
        try:
            installer.install(installer.own_executable(), spare)
        except Exception:
            log.exception("Échec de l'installation")
            return 1
        return 0

    purge = installer.PURGE_ARGUMENT in argv
    if not silent:
        go, purge = setup_dialog.confirm_uninstall()
        if not go:
            return 0
    if elevated:
        try:
            installer.uninstall(spare)
        except Exception:
            log.exception("Échec de la désinstallation")
            return 1
        installer.after_uninstall(purge)
        return 0

    installer.stop_instances()
    try:
        code = elevation.run_elevated(
            [installer.UNINSTALL_ARGUMENT, installer.SILENT_ARGUMENT,
             *installer.spare_argument()])
    except elevation.ElevationCancelled:
        log.info("Désinstallation annulée à l'invite UAC")
        return 1
    except (OSError, TimeoutError) as exc:
        log.error("La désinstallation n'a pas pu démarrer : %s", exc)
        code = -1
    if code == 0:
        installer.after_uninstall(purge)
        if not silent:
            setup_dialog.show_message(f"{product.APP_NAME} has been uninstalled.")
    elif not silent:
        setup_dialog.show_message(
            f"The removal failed (code {code}). The log is in {paths.log_file()}.",
            error=True)
    return code


def _install_from_launcher(silent):
    """Install or update, from the account that launched the executable.

    This account stops its running instances, hands the privileged part to
    an elevated copy, then points its "Run with Windows" entry at the
    installed copy and starts it, not elevated.
    """
    from . import setup_dialog

    if not paths.is_frozen():
        log.error("Installation impossible depuis les sources : construire l'exécutable")
        if not silent:
            setup_dialog.show_message(
                "Only the built executable can be installed (run build.cmd).",
                error=True)
        return 1

    first_install = installer.installed_version() is None
    installer.stop_instances()
    try:
        code = elevation.run_elevated(
            [installer.INSTALL_ARGUMENT, *installer.spare_argument()])
    except elevation.ElevationCancelled:
        log.info("Installation annulée à l'invite UAC")
        return 1
    except (OSError, TimeoutError) as exc:
        log.error("L'installation n'a pas pu démarrer : %s", exc)
        code = -1
    if code != 0:
        if not silent:
            setup_dialog.show_message(
                f"The installation failed (code {code}). "
                f"The log is in {paths.log_file()}.",
                error=True)
        return code or 1

    installer.after_install(first_install)
    return 0
