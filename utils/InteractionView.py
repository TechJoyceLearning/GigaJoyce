from typing import Optional, Callable, Dict, List, Any
from discord import Interaction, TextChannel, Message, Embed
from discord.ui import View, Button, Select
from discord.ext.commands import Bot
from shared.types import ExtendedClient
from pyee.asyncio import AsyncIOEventEmitter
import asyncio
import uuid


class InteractionView(View, AsyncIOEventEmitter):
    """Interactive Discord UI view that also emits custom events.

    This view bridges `discord.ui.View` with an async event emitter, allowing
    callers to listen for lifecycle events like `"end"` (timeout/deletion) while
    still using standard Discord UI components (buttons/selects).

    Features:
      * Auto timeout and `"end"` emission with reason `"timeout"`.
      * Listens for `on_message_delete` to end with reason `"deleted"`.
      * Component `custom_id` normalization and namespacing with `view_id`.
      * Ability to clone a view with the same behavior.
    """
    def __init__(
        self,
        interaction: Interaction,
        channel: TextChannel,
        client: ExtendedClient,
        ephemeral: Optional[bool] = False,
        filter_func: Optional[Callable[[Interaction], bool]] = None,
        timeout: Optional[int] = 60,  # Timeout em segundos
        parent: Optional["InteractionView"] = None,
    ):
        """Create an `InteractionView`.

        Args:
            interaction: The original interaction that spawned this view.
            channel: Text channel for context/logging.
            client: Extended bot client.
            ephemeral: Whether the response should be ephemeral.
            filter_func: Optional predicate to filter accepted interactions.
            timeout: Timeout (seconds) before this view ends automatically.
            parent: Optional parent view if this is a clone.
        """

        View.__init__(self, timeout=timeout)
        AsyncIOEventEmitter.__init__(self)

        self.interaction = interaction
        self.channel = channel
        self.client = client
        self.ephemeral = ephemeral
        self.filter_func = filter_func or (lambda i: True)
        self.parent = parent
        self.msg_id: Optional[str] = str(interaction.message.id) if interaction.message else None
        self.view_id: str = self._generate_random_id()
        self._timeout_task: Optional[asyncio.Task] = None

        self.client.add_listener(self._handle_message_delete, "on_message_delete")

        if self.timeout is not None and self.timeout > 0:
            self.start_timeout()

        self.client.logger.debug(f"InteractionView initialized with view_id: {self.view_id}, message ID: {self.msg_id}, ephemeral: {self.ephemeral}")

    @staticmethod
    def _generate_random_id() -> str:
        """Generate a unique identifier for this view instance.

        Returns:
            A UUID4 string.
        """
        return str(uuid.uuid4())

    async def on_timeout(self):
        """Called by discord.py when the view times out.

        Emits the `"end"` event with reason `"timeout"` and destroys the view.
        """
        self.client.logger.debug(f"View with view_id {self.view_id} has timed out.")
        self.emit("end", "timeout")
        self.destroy("timeout")

    async def _handle_message_delete(self, message: Message):
        """Internal listener to end the view if its message was deleted.

        Args:
            message: The deleted message.
        """
        if message.id == self.msg_id:
            self.client.logger.debug(f"Message with ID {self.msg_id} was deleted, triggering view destruction.")
            self.emit("end", "deleted")
            self.destroy("deleted")

    def start_timeout(self):
        """(Re)start the internal timeout task."""
        if self._timeout_task:
            self._timeout_task.cancel()
        self.client.logger.debug(f"Starting timeout for view with view_id: {self.view_id}")
        self._timeout_task = asyncio.create_task(self._timeout_handler())

    async def _timeout_handler(self):
        """Sleep for `self.timeout` seconds then trigger `on_timeout`."""
        await asyncio.sleep(self.timeout if self.timeout is not None else 0)
        await self.on_timeout()

    async def update(self, **kwargs) -> bool:
        """Update the message associated with this view.

        Keyword Args:
            components: Optional iterable of components (Buttons/Selects) to add.
            Any other arguments accepted by
            `interaction.edit_original_response` or `interaction.response.send_message`.

        Returns:
            True if the update succeeds, False otherwise.
        """
        try:
            components = kwargs.pop("components", [])
            self.client.logger.debug(f"Updating view with components: {components}")
            self.clear_items()
            for component in components:
                component = self._add_custom_id(component)
                self.add_item(component)

            if self.interaction.response.is_done():
                await self.interaction.edit_original_response(view=self, **kwargs)
            else:
                await self.interaction.response.send_message(view=self, **kwargs, ephemeral=self.ephemeral)
            self.client.logger.debug("View updated successfully.")
            return True
        except Exception as e:
            self.client.logger.error(f"Failed to update interaction view: {e}")
            return False

    def _add_custom_id(self, component: Any) -> Any:
        """Ensure the component `custom_id` includes this view's `view_id`.

        This namespaces component identifiers so callbacks can distinguish
        between multiple active views.

        Args:
            component: A Discord UI component instance.

        Returns:
            The same component, potentially with a modified `custom_id`.
        """
        if hasattr(component, "custom_id") and component.custom_id:
            split_id = component.custom_id.split("-")
            if len(split_id) > 1 and "-".join(split_id[1:]) == self.view_id:
                return component 
            component.custom_id = f"{component.custom_id}-{self.view_id}"
            self.client.logger.debug(f"Updated custom_id for component: {component.custom_id} | View Id: {self.view_id}")
        return component
    
    def normalize_custom_id(self, custom_id: str) -> str:
        """Strip the view_id suffix from a component `custom_id`, if present.

        Args:
            custom_id: The raw custom id from an interaction component.

        Returns:
            The normalized id without the view suffix.
        """
        normalized_id = custom_id.split("-")[0] if "-" in custom_id else custom_id
        self.client.logger.debug(f"Normalized custom_id: {custom_id} -> {normalized_id}")
        return normalized_id
    
    def clone(self) -> "InteractionView":
        """Create a shallow clone of this view.

        Returns:
            A new `InteractionView` with the same config and `msg_id`.
        """
        self.client.logger.debug(f"Cloning InteractionView with view_id: {self.view_id}")
        cloned_view = InteractionView(
            interaction=self.interaction,
            channel=self.channel,
            client=self.client,
            ephemeral=self.ephemeral,
            filter_func=self.filter_func,
            timeout=int(self.timeout) if self.timeout is not None else None,
            parent=self
        )
        cloned_view.set_msg_id(self.msg_id)
        return cloned_view

    def set_msg_id(self, msg_id: Optional[str]):
        """Attach a message id to this view instance.

        Args:
            msg_id: The Discord message id to associate.
        """
        self.msg_id = msg_id
        self.client.logger.debug(f"Message ID set for view: {msg_id}")

    def destroy(self, reason: Optional[str] = None):
        """Tear down the view and unregister listeners.

        Args:
            reason: Optional reason for diagnostics (e.g., `"timeout"`).
        """
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None

        if self.client.view_registry and self.msg_id in self.client.view_registry:
            del self.client.view_registry[self.msg_id]

        self.emit("end", reason or "destroy")
        self.clear_items() 

        if "on_message_delete" in self._events:
            self.client.remove_listener(self._handle_message_delete, "on_message_delete")

        self.stop()  
        self.client.logger.debug(f"InteractionView with view_id {self.view_id}, {reason}.")
    
    def set_extra_filter(self, filter_func: Callable[[Interaction], bool]):
        """Set an additional interaction filter predicate.

        Args:
            filter_func: Callable that receives an `Interaction` and returns `True`
                if it should be handled by this view, `False` otherwise.
        """
        self.filter_func = filter_func
        self.client.logger.debug(f"Extra filter function set for InteractionView {self.view_id}")
