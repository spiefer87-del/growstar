//
// --------------------------------------------
// Growstar Dialog
// --------------------------------------------

function showDialog(title,text){

    document
    .getElementById("dialog-title")
    .textContent = title;

    document
    .getElementById("dialog-content")
    .textContent = text;

    document
    .getElementById("dialog")
    .style.display = "flex";

}



function closeDialog(){

    document
    .getElementById("dialog")
    .style.display = "none";

}



window.addEventListener(

    "DOMContentLoaded",

    ()=>{

        document
        .getElementById("dialog-close")
        ?.addEventListener(

            "click",

            closeDialog

        );

    }

);
