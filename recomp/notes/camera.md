# The camera limit block

Recovered from `hhcamera_apply_angle_limits` at **0x00111EE8** (`../hahig/hhcamera.c`),
which is the function that turns "where the camera would like to look" into
"where the game lets it look".

## Where the struct is

    camera = *(void**)(scene + 0xE4)

Same pointer the freecam notes already used. Everything below is an offset
into `camera`, and every angle is a **binary angle**: 65536 = 360 degrees.
The function proves it twice -- it converts for display with `v * 360 >> 16`,
and for maths with `v * pi * (1/32768)`.

## Layout

    +0x1D0  u16   centre angle X   (yaw the camera is anchored to)
    +0x1D2  u16   centre angle Y   (pitch)
    +0x1D4  u16   range X          (how far either side of centre it may go)
    +0x1D6  u16   range Y
    +0x1D8  u16   roll, handed to hhcamera_set_lookat unchanged

The debug rows the function prints name these directly:

    CAMERA CENTER      <- 0x1D0, 0x1D2
    CAMERA RANGE       <- 0x1D4, 0x1D6
    CAMERA MIN         <- centre - range
    CAMERA MAX         <- centre + range
    CAMERA ORIG ANGLE  <- asinf/atan2f of the normalised look vector, before clamping
    CAMERA LIMIT ANGLE <- the clamped result actually used

## The unlock

The very first thing the function does is a 64-bit load of `+0x1D0` masked to
its upper half -- which on this little-endian target is the **two range
halfwords**, not the centres:

    ld    v0, 0x1D0(camera)
    and   v0, 0xFFFFFFFF00000000
    bne   v0, 0x8000800000000000, <clamp path>

So if `range X == 0x8000` and `range Y == 0x8000`, the whole clamp is skipped
and the look angle goes to `hhcamera_set_lookat` untouched.

    write 0x8000 to camera+0x1D4 and camera+0x1D6  ->  unrestricted camera

That value is safe even if some other path reaches the clamp anyway: 0x8000 is
180 degrees, so `centre +/- range` covers the entire circle and the two
comparisons can never fire.

## Position

The same function reads the world position of two objects at `+0x30/+0x34/+0x38`
(x, y, z floats) and subtracts them to get the look vector -- confirming the
`+0x30` position offset, and that the camera aims at a *target object* rather
than at a stored angle.
