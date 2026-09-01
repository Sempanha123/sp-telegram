# Compatibility layer for dialog classes to support older PySide6 versions
# This file should be imported by dialog classes that use QDialog.DialogCode

from PySide6.QtWidgets import QDialog

# Monkey-patch QDialog to add Accepted and Rejected class attributes
# if they don't already exist (for PySide6 < 6.4)
if not hasattr(QDialog, 'Accepted'):
    QDialog.Accepted = QDialog.DialogCode.Accepted

if not hasattr(QDialog, 'Rejected'):
    QDialog.Rejected = QDialog.DialogCode.Rejected