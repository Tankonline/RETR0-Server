# Project RETR0 - built-in local-server redirect for Real Racing 3 14.0.1 (independently written).
# Same behaviour as 08_TESTING/runtime/retr0_redirect_java.js in 'redirect' mode, without Frida:
# HttpRequest.init() calls rewrite(url) first; a request to a CloudCell host (*.cloudcell.com, *.exos.fm)
# or the asset CDN (firemonkeys.akamaized.net) goes to http://127.0.0.1:8780<path+query> instead.
# finish(request) then adds header X-RETR0-Host: <original host> (the local server routes CDN packs on it).
# Every other URL is left unchanged. The emulator reaches the PC through `adb reverse tcp:8780 tcp:8780`.
.class public final Lcom/retr0/Redirect;
.super Ljava/lang/Object;

.field private static final HOST:Ljava/lang/ThreadLocal;

.method static constructor <clinit>()V
    .locals 1
    new-instance v0, Ljava/lang/ThreadLocal;
    invoke-direct {v0}, Ljava/lang/ThreadLocal;-><init>()V
    sput-object v0, Lcom/retr0/Redirect;->HOST:Ljava/lang/ThreadLocal;
    return-void
.end method

.method public static rewrite(Ljava/lang/String;)Ljava/lang/String;
    .locals 5
    sget-object v0, Lcom/retr0/Redirect;->HOST:Ljava/lang/ThreadLocal;
    const/4 v1, 0x0
    invoke-virtual {v0, v1}, Ljava/lang/ThreadLocal;->set(Ljava/lang/Object;)V
    if-nez p0, :have_url
    return-object p0
    :have_url
    const-string v1, "^[hH][tT][tT][pP][sS]?://([^/:?#]+)(?::[0-9]+)?(.*)$"
    invoke-static {v1}, Ljava/util/regex/Pattern;->compile(Ljava/lang/String;)Ljava/util/regex/Pattern;
    move-result-object v1
    invoke-virtual {v1, p0}, Ljava/util/regex/Pattern;->matcher(Ljava/lang/CharSequence;)Ljava/util/regex/Matcher;
    move-result-object v1
    invoke-virtual {v1}, Ljava/util/regex/Matcher;->matches()Z
    move-result v2
    if-nez v2, :parsed
    return-object p0
    :parsed
    const/4 v2, 0x1
    invoke-virtual {v1, v2}, Ljava/util/regex/Matcher;->group(I)Ljava/lang/String;
    move-result-object v2
    const-string v3, "(?i)(.*[.])?cloudcell[.]com|(.*[.])?exos[.]fm|firemonkeys[.]akamaized[.]net"
    invoke-virtual {v2, v3}, Ljava/lang/String;->matches(Ljava/lang/String;)Z
    move-result v3
    if-nez v3, :redirect
    return-object p0
    :redirect
    invoke-virtual {v0, v2}, Ljava/lang/ThreadLocal;->set(Ljava/lang/Object;)V
    const/4 v3, 0x2
    invoke-virtual {v1, v3}, Ljava/util/regex/Matcher;->group(I)Ljava/lang/String;
    move-result-object v3
    const-string v4, "/"
    invoke-virtual {v3, v4}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v1
    if-nez v1, :has_slash
    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {v1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3
    :has_slash
    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V
    const-string v4, "http://127.0.0.1:8780"
    invoke-virtual {v1, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v1
    return-object v1
.end method

.method public static finish(Lcom/firemonkeys/cloudcellapi/HttpRequest;)V
    .locals 3
    sget-object v0, Lcom/retr0/Redirect;->HOST:Ljava/lang/ThreadLocal;
    invoke-virtual {v0}, Ljava/lang/ThreadLocal;->get()Ljava/lang/Object;
    move-result-object v1
    if-eqz v1, :done
    const/4 v2, 0x0
    invoke-virtual {v0, v2}, Ljava/lang/ThreadLocal;->set(Ljava/lang/Object;)V
    check-cast v1, Ljava/lang/String;
    const-string v2, "X-RETR0-Host"
    invoke-virtual {p0, v2, v1}, Lcom/firemonkeys/cloudcellapi/HttpRequest;->addHeader(Ljava/lang/String;Ljava/lang/String;)V
    :done
    return-void
.end method
