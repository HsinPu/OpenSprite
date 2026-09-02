# Windows installer native cleanup

The isolated Windows installer test now quarantines pywin32 native DLLs as well
as Python extension modules before uninstall cleanup. This avoids transient
Windows loader locks on `pywintypes` without weakening path validation or
changing the production installation payload.
