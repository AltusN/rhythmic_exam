function countdown(hrs, mins, show_seconds){
    let hours, minutes, seconds;
    var end_date = new Date();

    end_date.setHours(end_date.getHours() + hrs);
    end_date.setMinutes(end_date.getMinutes() + mins);
    
    setInterval(calculate, 1000);

    function calculate(){
        let start_date = new Date();
        start_date = start_date.getTime();

        let remaining_time = parseInt((end_date - start_date)/1000);

        if (remaining_time >= 0){
            days = parseInt(remaining_time / 86400);
            remaining_time = (remaining_time % 86400);

            hours = parseInt(remaining_time / 3600);
            remaining_time = (remaining_time % 3600);

            minutes = parseInt(remaining_time / 60);
            remaining_time = (remaining_time % 60);

            seconds = parseInt(remaining_time);
            if(show_seconds){
                document.getElementById("countdown").innerHTML = hours + "h " + minutes + "m " + seconds + "s ";
            } else{
                document.getElementById("countdown").innerHTML = hours + "h " + minutes + "m ";
            }

            return true;
        } else{
            return false;
        }
    }
}

function submitForm(formname){
    if (!formname){
        formname="exam";
    }
    window.onbeforeunload = null;
    document.getElementById(formname).submit();
}

function startCountDown(hrs, mins, show_seconds, formname){
    countdown(hrs,mins, show_seconds);
    setTimeout(submitForm, (parseInt(mins) * 60 * 1000), formname);
}