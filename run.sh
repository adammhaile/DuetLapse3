IP=$1
BASEURL="http://${IP}/cam.cgi"

OUTDIR=$2

init_camera() {
    URL="${BASEURL}?mode=camcmd&value=recmode"
    echo ${URL}
    curl ${URL}
    echo ""
}

CAPTURE_URL="${BASEURL}?mode=camcmd&value=capture"

capture_frame() {
    URL="${BASEURL}?mode=camcmd&value=capture"
    echo ${URL}
    curl ${URL}
    echo ""
    return 0
}

rec_start() {
    URL="${BASEURL}?mode=camcmd&value=video_recstart"
    echo ${URL}
    curl ${URL}
    echo ""
}

rec_stop() {
    URL="${BASEURL}?mode=camcmd&value=video_recstop"
    echo ${URL}
    curl ${URL}
    echo ""
}

init_camera

python3 DuetLapse3.py -duet rancor -basedir ${OUTDIR} -port 8080 \
    -detect layer \
    -camera1 web \
    -weburl1 ${CAPTURE_URL}
    #-camparam1 "'curl ${CAPTURE_URL} -o ' + fn + debug"