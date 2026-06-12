# =============================================================================
# Source: pypylon official GitHub repository
#   https://github.com/basler/pypylon/blob/master/samples/ConfigurationEventPrinter.py
#
# PURPOSE OF THIS FILE
# --------------------
# This file defines a *configuration event handler* — a class that lets your
# code react to every major lifecycle event of a Basler camera (opening,
# closing, grabbing starting/stopping, errors, disconnection, etc.).
#
# Think of it as a series of "hooks" that pypylon automatically calls at the
# right moment. You don't call these methods yourself — you register the class
# with the camera and pypylon calls them for you.
#
# HOW EVENT HANDLERS WORK IN PYPYLON
# ------------------------------------
# pypylon uses the Observer pattern (also called the callback or listener pattern):
#   1. You write a class that inherits from one of pypylon's base handler classes.
#   2. You override the methods (events) you care about.
#   3. You register an instance of your class with the camera via:
#        camera.RegisterConfiguration(YourHandler(), ...)
#   4. pypylon calls your overridden methods automatically when those events fire.
#
# This file is a *diagnostic* handler — it just prints each event so you can
# see the exact sequence pypylon fires them during a session. In real code you
# would replace the print() calls with actual logic (logging, state machines,
# hardware interlocks, etc.).
# =============================================================================

from pypylon import pylon
# Import the pylon namespace. Everything pypylon-related lives here.
# pylon.ConfigurationEventHandler (used below) is the base class we must inherit.


# =============================================================================
# CLASS DEFINITION
# =============================================================================

class ConfigurationEventPrinter(pylon.ConfigurationEventHandler):
    # We inherit from pylon.ConfigurationEventHandler.
    # This base class defines all the event methods with empty (no-op) bodies.
    # By subclassing it, we only need to override the events we care about —
    # any event we do NOT override is silently ignored (the base no-op runs).
    #
    # Python inheritance syntax reminder:
    #   class ChildClass(ParentClass):   ← ChildClass inherits everything from ParentClass
    #
    # Alternative base classes for other handler types:
    #   pylon.ImageEventHandler          → reacts to image grab events (OnImageGrabbed, etc.)
    #   pylon.CameraEventHandler         → reacts to GenICam camera events (e.g. exposure end)
    # This file only covers ConfigurationEventHandler (lifecycle events).

    # =========================================================================
    # ATTACHMENT EVENTS
    # These fire when the handler object is linked/unlinked to/from the camera.
    # "Attaching" = associating the handler with the camera object in software.
    # This is separate from the camera being physically connected or opened.
    # =========================================================================

    def OnAttach(self, camera):
        # Called BEFORE the handler is attached to the camera.
        # At this point the camera object exists but the handler is not yet registered.
        # 'camera' is passed in but GetDeviceInfo() may not yet be fully available,
        # which is why this print does NOT call GetModelName() — safer to omit it here.
        # Use this event to do any pre-attachment setup your handler needs.
        print("OnAttach event")

    def OnAttached(self, camera):
        # Called AFTER the handler has been successfully attached to the camera.
        # The camera object is now fully associated with this handler.
        # Safe to call camera.GetDeviceInfo() here.
        #
        # camera.GetDeviceInfo()      → returns a DeviceInfo object
        # .GetModelName()             → returns the camera model string, e.g. "acA1920-40gc"
        # Other DeviceInfo methods:   .GetSerialNumber(), .GetIpAddress(), .GetDeviceClass()
        print("OnAttached event for device ", camera.GetDeviceInfo().GetModelName())

    # =========================================================================
    # OPEN / CLOSE EVENTS
    # These fire when camera.Open() and camera.Close() are called.
    # "Open" = establishing the communication channel and making the GenICam
    # node map (parameters like exposure, gain, ROI) accessible.
    # Note the pattern: each action has a BEFORE (OnX) and AFTER (OnXed) variant.
    # =========================================================================

    def OnOpen(self, camera):
        # Called BEFORE camera.Open() executes its internal logic.
        # The camera connection is not yet established at this point.
        # Use this to prepare anything that must happen just before opening
        # (e.g. locking a mutex, logging a timestamp).
        print("OnOpen event for device ", camera.GetDeviceInfo().GetModelName())

    def OnOpened(self, camera):
        # Called AFTER camera.Open() completes successfully.
        # The camera is now open: the GenICam node map is live and you can
        # read/write parameters (exposure, gain, ROI, trigger mode, etc.).
        # This is the most common place to apply camera settings in a handler
        # — for example, SoftwareTriggerConfiguration does its work here.
        # If you write your own configuration class, put parameter writes inside
        # OnOpened() rather than OnOpen() to ensure the node map is ready.
        print("OnOpened event for device ", camera.GetDeviceInfo().GetModelName())

    def OnClose(self, camera):
        # Called BEFORE camera.Close() executes.
        # The camera is still open at this moment; you can still read parameters.
        # Use this to gracefully stop anything that depends on the camera being open
        # (e.g. flush a write buffer, log final parameter values).
        print("OnClose event for device ", camera.GetDeviceInfo().GetModelName())

    def OnClosed(self, camera):
        # Called AFTER camera.Close() completes.
        # The GenICam node map is no longer accessible — do not try to read
        # or write camera parameters here or you will get an exception.
        # Use this for cleanup that should happen only after the connection drops.
        print("OnClosed event for device ", camera.GetDeviceInfo().GetModelName())

    # =========================================================================
    # GRAB START / STOP EVENTS
    # These fire when camera.StartGrabbing() and camera.StopGrabbing() are called.
    # "Grabbing" = the grab engine is running, buffers are being filled by the camera.
    # Again: BEFORE (OnGrabStart) and AFTER (OnGrabStarted) variants exist.
    # =========================================================================

    def OnGrabStart(self, camera):
        # Called BEFORE the grab engine starts (before buffers are allocated and
        # queued to the camera).
        # Use this to reset frame counters, arm external hardware, or start a timer.
        print("OnGrabStart event for device ", camera.GetDeviceInfo().GetModelName())

    def OnGrabStarted(self, camera):
        # Called AFTER the grab engine has started successfully.
        # Buffers are now queued; the camera will start filling them.
        # This is a reliable signal that acquisition is truly underway.
        print("OnGrabStarted event for device ", camera.GetDeviceInfo().GetModelName())

    def OnGrabStop(self, camera):
        # Called BEFORE the grab engine stops (before buffers are deallocated).
        # Use this to signal worker threads to stop, or to save a "last frame" snapshot.
        print("OnGrabStop event for device ", camera.GetDeviceInfo().GetModelName())

    def OnGrabStopped(self, camera):
        # Called AFTER the grab engine has fully stopped and all buffers are freed.
        # Safe to release any resources that were being used during acquisition.
        print("OnGrabStopped event for device ", camera.GetDeviceInfo().GetModelName())

    # =========================================================================
    # DESTROY EVENTS
    # These fire when the InstantCamera object itself is being destroyed
    # (i.e. going out of scope / garbage collected in Python, or explicitly deleted).
    # This is the deepest level of teardown — below Close.
    # =========================================================================

    def OnDestroy(self, camera):
        # Called BEFORE the camera object is destroyed.
        # The camera is still accessible here (though it should already be closed).
        # Last chance to read identifying information before the object disappears.
        print("OnDestroy event for device ", camera.GetDeviceInfo().GetModelName())

    def OnDestroyed(self, camera):
        # Called AFTER the camera object has been destroyed.
        # 'camera' is passed but its internal device handle is gone — do NOT
        # call GetDeviceInfo() or any camera method here; it will crash.
        # This is why this print has no GetModelName() call (see OnAttach for
        # the same reasoning in the other direction).
        # Use this only to clean up handler-internal state that doesn't touch the camera.
        print("OnDestroyed event")

    # =========================================================================
    # DETACH EVENTS
    # These fire when the handler is unregistered from the camera.
    # "Detaching" = the handler object is being dissociated from the camera in software.
    # Opposite of Attach. Triggered by DeregisterConfiguration() or when the
    # camera object is destroyed with Cleanup_Delete set.
    # =========================================================================

    def OnDetach(self, camera):
        # Called BEFORE the handler is detached from the camera.
        # The handler is still registered; the camera is still accessible.
        print("OnDetach event for device ", camera.GetDeviceInfo().GetModelName())

    def OnDetached(self, camera):
        # Called AFTER the handler has been detached from the camera.
        # The handler is no longer registered. The camera may still exist
        # (if other handlers are still attached), or may be in the process
        # of being destroyed. Safe to call GetDeviceInfo() here.
        print("OnDetached event for device ", camera.GetDeviceInfo().GetModelName())

    # =========================================================================
    # ERROR EVENT
    # =========================================================================

    def OnGrabError(self, camera, errorMessage):
        # Called when a grab operation encounters an error — e.g. a corrupted
        # packet on GigE, a buffer underflow, or a transport layer fault.
        # This does NOT necessarily mean grabbing has stopped; the grab engine
        # may continue and recover on the next frame depending on the error type.
        #
        # 'errorMessage' is a string describing the fault.
        # In production code you would log this to a file, increment an error
        # counter, or trigger an alarm rather than just printing.
        #
        # Note the extra parameter compared to other methods:
        #   def OnGrabError(self, camera, errorMessage)  ← two args after self
        # All other event methods only receive 'camera'. errorMessage is unique here.
        print("OnGrabError event for device ", camera.GetDeviceInfo().GetModelName())
        print("Error Message: ", errorMessage)

    # =========================================================================
    # HARDWARE DISCONNECTION EVENT
    # =========================================================================

    def OnCameraDeviceRemoved(self, camera):
        # Called when the physical camera is unexpectedly disconnected while the
        # camera object is still open — e.g. a USB cable is pulled, or a GigE
        # link goes down.
        # This is NOT the same as a normal Close/Detach sequence.
        # After this event fires, the camera object is in an error state.
        # You should call camera.Close() and handle reconnection logic here.
        # In a lab setting this is critical to handle gracefully so your experiment
        # does not silently drop data — log the event and alert the operator.
        print("OnCameraDeviceRemoved event for device ", camera.GetDeviceInfo().GetModelName())


# =============================================================================
# COMPLETE LIFECYCLE EVENT ORDER (for reference)
# =============================================================================
# When you run a typical grab session, events fire in this order:
#
#   camera.RegisterConfiguration(handler)
#       → OnAttach
#       → OnAttached
#
#   camera.Open()
#       → OnOpen
#       → OnOpened           ← apply camera settings here in your own handlers
#
#   camera.StartGrabbing()
#       → OnGrabStart
#       → OnGrabStarted
#
#   ... grabbing frames ...  (OnGrabError fires here if something goes wrong)
#   ... cable pulled?        (OnCameraDeviceRemoved fires here)
#
#   camera.StopGrabbing()
#       → OnGrabStop
#       → OnGrabStopped
#
#   camera.Close()
#       → OnClose
#       → OnClosed
#
#   camera object destroyed (goes out of scope or del camera)
#       → OnDestroy
#       → OnDetach
#       → OnDetached
#       → OnDestroyed
#
# HOW TO USE THIS CLASS IN YOUR OWN SCRIPT
# -----------------------------------------
#   from configuration_event import ConfigurationEventPrinter
#   from pypylon import pylon
#
#   camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
#   camera.RegisterConfiguration(
#       ConfigurationEventPrinter(),
#       pylon.RegistrationMode_Append,   # keep other handlers, add this one too
#       pylon.Cleanup_Delete             # pypylon frees the object when done
#   )
#   camera.Open()    # triggers OnAttach → OnAttached → OnOpen → OnOpened
#   ...
# =============================================================================
