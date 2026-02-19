from vkmax.functions.uploads import UploadMethods
from vkmax.functions.users import UserMethods
from vkmax.functions.profile import ProfileMethods
from vkmax.functions.messages import MessageMethods
from vkmax.functions.groups import GroupMethods
from vkmax.functions.channels import ChannelMethods


class MaxClient(
    UserMethods,
    ProfileMethods,
    MessageMethods,
    GroupMethods,
    ChannelMethods,
    UploadMethods,
):
    pass

__all__ = ["MaxClient"]