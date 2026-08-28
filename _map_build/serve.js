const http=require("http"),fs=require("fs"),path=require("path");
const DIR=path.join(__dirname,"serve");
http.createServer((req,res)=>{
  if(req.method==="POST"&&req.url.startsWith("/shot")){
    const name=(new URL(req.url,"http://x").searchParams.get("n")||"shot")+".png";
    let body="";req.on("data",c=>body+=c);
    req.on("end",()=>{fs.writeFileSync(path.join(__dirname,name),
      Buffer.from(body.replace(/^data:image\/png;base64,/,""),"base64"));
      res.writeHead(200,{"Access-Control-Allow-Origin":"*"});res.end("ok "+name);});
    return;
  }
  fs.readFile(path.join(DIR,"index.html"),(e,buf)=>{
    if(e){res.writeHead(500);return res.end(String(e));}
    res.writeHead(200,{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store"});
    res.end(buf);});
}).listen(8731,()=>console.log("serving on http://localhost:8731"));
