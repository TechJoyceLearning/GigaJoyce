import os
from dotenv import load_dotenv
import motor.motor_asyncio

load_dotenv()

MONGODB_TOKEN = os.getenv("MONGODB_TOKEN")

class MongoDBAsyncORM:
    """Thin convenience layer over Motor's AsyncIOMotorClient.

    Wraps client/database initialization and provides common CRUD helpers and
    index creation with concise signatures.

    Args:
        uri: MongoDB connection URI (compatible with Motor).
        db_name: Database name to bind to.

    Attributes:
        client: `AsyncIOMotorClient` instance.
        db: Selected database handle.
    """
    def __init__(self, uri, db_name="database"):
        """
        Initialize the MongoDBAsyncORM instance.
        """
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.client[db_name]

    def get_collection(self, collection_name):
        """Return a collection handle by name.

        Args:
            collection_name: Collection name.

        Returns:
            The `AsyncIOMotorCollection` associated with `collection_name`.
        """
        return self.db[collection_name]
    
    async def create_index(self, collection_name, keys, unique=False):
        """Create an index on a collection.

        If `unique=True`, uniqueness is enforced.

        Args:
            collection_name: Target collection.
            keys: List of (field, direction) pairs, e.g. `[("id", 1), ("guildId", 1)]`.
            unique: Whether the index should be unique.

        Returns:
            The created index name.
        """
        collection = self.get_collection(collection_name)
        index_name = await collection.create_index(keys, unique=unique)
        return index_name

    async def insert_one(self, collection_name, document):
        """Insert a single document.

        Args:
            collection_name: Target collection.
            document: Document to insert.

        Returns:
            The inserted document id.
        """
        collection = self.get_collection(collection_name)
        result = await collection.insert_one(document)
        return result.inserted_id

    async def insert_many(self, collection_name, documents):
        """Insert multiple documents.

        Args:
            collection_name: Target collection.
            documents: List of documents to insert.

        Returns:
            List of inserted ids.
        """
        collection = self.get_collection(collection_name)
        result = await collection.insert_many(documents)
        return result.inserted_ids

    async def find_one(self, collection_name, query, projection=None):
        """Find a single document.

        Args:
            collection_name: Target collection.
            query: Filter document.
            projection: Optional projection.

        Returns:
            The matched document or `None`.
        """
        collection = self.get_collection(collection_name)
        return await collection.find_one(query, projection)

    async def find(self, collection_name, query, projection=None):
        """Find multiple documents.

        Args:
            collection_name: Target collection.
            query: Filter document.
            projection: Optional projection.

        Returns:
            All matched documents as a list.
        """
        collection = self.get_collection(collection_name)
        cursor = collection.find(query, projection)
        return await cursor.to_list(length=None)

    async def update_one(self, collection_name, query, update, upsert=False):
        """Update a single document.

        If `update` contains no Mongo operator (like `$set`), it is automatically
        wrapped as `{"$set": update}` for convenience.

        Args:
            collection_name: Target collection.
            query: Filter to select the document.
            update: Update document with or without Mongo operators.
            upsert: Create the document if no match is found.

        Returns:
            The number of documents modified.
        """
        collection = self.get_collection(collection_name)

        if not any(key.startswith('$') for key in update.keys()):
            update = {"$set": update}

        result = await collection.update_one(query, update, upsert=upsert)
        return result.modified_count


    async def delete_one(self, collection_name, query):
        """Delete a single document.

        Args:
            collection_name: Target collection.
            query: Deletion filter.

        Returns:
            The number of documents deleted.
        """
        collection = self.get_collection(collection_name)
        result = await collection.delete_one(query)
        return result.deleted_count

    async def count_documents(self, collection_name, query={}):
        """Count documents in a collection.

        Args:
            collection_name: Target collection.
            query: Optional filter. Counts all documents if omitted.

        Returns:
            The count of matching documents.
        """
        collection = self.get_collection(collection_name)
        return await collection.count_documents(query)

    async def list_collections(self):
        """List all collections in the current database.

        Returns:
            List of collection names.
        """
        return await self.db.list_collection_names()

    async def ensure_guild_structure(self, module_name, structure):
        """Ensure a per-guild structure exists for a given module.

        Iterates over the `guilds` collection, derives a guild-specific collection name,
        and inserts the default `structure` for `module_name` if missing.

        Args:
            module_name: Module name, e.g. `"XPSystem"`.
            structure: Default structure to ensure.
        """
        guilds = await self.find("guilds", {})  # Assuming a 'guilds' collection exists
        for guild in guilds:
            guild_id = guild.get("guild_id")
            if not guild_id:
                continue

            collection_name = f"guild_{guild_id}"  # Example pattern for guild-specific collections
            existing_data = await self.find_one(collection_name, {"module_name": module_name})

            if not existing_data:
                await self.insert_one(collection_name, {
                    "module_name": module_name,
                    **structure
                })

    async def close(self):
        """
        Close the connection to the MongoDB database.
        """
        self.client.close()
        print("Closed MongoDB connection")
