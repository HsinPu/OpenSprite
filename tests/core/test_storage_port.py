from opensprite.core.ports.storage import StorageProvider


def test_storage_port_abstract_method_set_is_stable():
    assert StorageProvider.__abstractmethods__ == {
        "add_message",
        "add_run_event",
        "add_run_file_change",
        "add_run_part",
        "clear_messages",
        "create_run",
        "get_all_sessions",
        "get_background_process",
        "get_consolidated_index",
        "get_messages",
        "get_run_events",
        "get_run_file_changes",
        "get_run_parts",
        "get_runs",
        "list_background_processes",
        "set_consolidated_index",
        "update_run_status",
        "upsert_background_process",
    }


def test_storage_port_keeps_default_helper_methods():
    expected_helpers = {
        "get_latest_run",
        "get_message_count",
        "get_messages_slice",
        "get_recent_sessions",
        "get_run",
        "get_run_file_change",
        "get_run_trace",
    }

    assert expected_helpers <= set(StorageProvider.__dict__)
