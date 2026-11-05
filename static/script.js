const imgs=document.querySelectorAll('.slide')
let i=0,timer
function show(step=1){
  imgs[i].hidden=true
  i=(i+step+imgs.length)%imgs.length
  imgs[i].hidden=false
  clearTimeout(timer)
  timer=setTimeout(show,3000)
}
if(imgs.length){
  for(const b of document.querySelectorAll('[data-step]')) b.onclick=()=>show(+b.dataset.step)
  show(0)
}
