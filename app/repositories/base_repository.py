"""Base repository with common CRUD operations for all repositories."""

from typing import Dict, List, Optional, Any

from supabase import Client


class BaseRepository:
    """Base repository providing common CRUD operations.

    Encapsulates standard database operations that are shared across
    all repositories, reducing code duplication and ensuring consistency.

    Attributes:
        db_client: Supabase client instance for database operations.
        table_name: Name of the database table this repository manages.
    """

    def __init__(self, db_client: Client, table_name: str):
        """Initialize the base repository.

        Args:
            db_client: Supabase client instance.
            table_name: Name of the database table (e.g., "candidates", "companies").
        """
        self.db_client = db_client
        self.table_name = table_name

    def get_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single record by its ID.

        Args:
            record_id: The unique identifier of the record.

        Returns:
            Record as dictionary if found, None otherwise.

        Raises:
            Exception: If database query fails.
        """
        try:
            response = (
                self.db_client.table(self.table_name)
                .select("*")
                .eq("id", record_id)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as error:
            raise Exception(f"Failed to get {self.table_name} by ID: {str(error)}")

    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all records from the table.

        Returns:
            List of records as dictionaries.

        Raises:
            Exception: If database query fails.

        Note:
            This loads all records into memory. Consider pagination for
            large datasets.
        """
        try:
            response = self.db_client.table(self.table_name).select("*").execute()
            return response.data
        except Exception as error:
            raise Exception(f"Failed to get all {self.table_name}: {str(error)}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record into the table.

        Args:
            data: Dictionary containing record data matching the table schema.

        Returns:
            Dictionary containing the inserted record.

        Raises:
            Exception: If insertion fails (e.g., duplicate key, constraint violation).
        """
        try:
            response = self.db_client.table(self.table_name).insert(data).execute()
            return response.data[0] if response.data else {}
        except Exception as error:
            raise Exception(f"Failed to create {self.table_name}: {str(error)}")

    def update(self, record_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a record with new data.

        Args:
            record_id: The unique identifier of the record to update.
            updates: Dictionary of fields to update.

        Returns:
            Updated record as dictionary.

        Raises:
            Exception: If update fails or record not found.
        """
        try:
            response = (
                self.db_client.table(self.table_name)
                .update(updates)
                .eq("id", record_id)
                .execute()
            )

            if not response.data:
                raise Exception(f"{self.table_name.capitalize()} with ID {record_id} not found")

            return response.data[0]
        except Exception as error:
            raise Exception(f"Failed to update {self.table_name}: {str(error)}")

    def delete(self, record_id: str) -> bool:
        """Delete a record from the table.

        Args:
            record_id: The unique identifier of the record to delete.

        Returns:
            True if deletion was successful.

        Raises:
            Exception: If deletion fails.
        """
        try:
            response = (
                self.db_client.table(self.table_name)
                .delete()
                .eq("id", record_id)
                .execute()
            )
            return True
        except Exception as error:
            raise Exception(f"Failed to delete {self.table_name}: {str(error)}")
