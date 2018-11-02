from enum import Enum, auto


class Status(Enum):
    # Prefix
    # C: Client, R: RequestBroker, W: Worker

    # Client -> RequestBroker
    CR_SentRequest = auto()      # notice
    CR_ReceivedRequest = auto()

    # RequestBroker -> Worker
    RW_SentCommand = auto()      # notice
    RW_SentAllCommands = auto()  # notice
    RW_ReceivedCommand = auto()  # notice

    # Worker -> RequestBroker
    WR_ReceivedResult = auto()   # notice
    WR_CollectingResults = auto()
    WR_ReceivedAllResults = auto()

    # RequestBroker -> Client
    RC_ReceivedRequestID = auto()   # notice
    RC_SentResult = auto()
    RC_ReceivedResult = auto()      # notice

    # only in Workers
    WR_SentNotice = auto()
    WR_SentResult = auto()

    # Error
    # RequestBroker -> Client
    RC_RequestError = auto()
    RC_TimeoutError = auto()

    def __str__(self):
        return self.name


CompletedStatus = [Status.RC_SentResult,
                   Status.RC_TimeoutError,
                   Status.RC_RequestError]
