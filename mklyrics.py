#!/usr/bin/env python3

from argparse import ArgumentParser
from threading import Thread
import readchar
import subprocess
import sys

class PlayerThread(Thread):
    def __init__(self, filename, starttime=0):
        super().__init__()
        self.player = Mpg321(filename, starttime)

    def run(self):
        self.player.play()
        while self.player.media_process.poll() is None:
            self.outputline = self.player.read()

    def toggle(self):
        self.player.toggle()

    def kill(self):
        self.player.kill()

    def jump(self, time):
        self.player.jump(time)

    def gettime(self):
        try:
            return float(self.outputline.split(b' ')[3])
        except:
            return 0.0


class Mpg321:
    def __init__(self, filename, starttime=0):
        self.filename = filename
        self.starttime = starttime

    def jump(self, time):
        self.send("J {}s".format(time))

    def send(self, command):
        bytes_command = bytes(command + "\n", "utf8")
        #print(">" + str(bytes_command))
        self.media_process.stdin.write(bytes_command)
        self.media_process.stdin.flush()

    def play(self):
        self.media_process = subprocess.Popen(["mpg123", "-b", "512", "-R",
                                               "--remote-err"],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self.send("load {}".format(self.filename))
        self.jump(self.starttime)

    def read(self):
        output = self.media_process.stderr.readline()
        #print("<" + str(output))
        return output

    def toggle(self):
        self.send("pause")

    def kill(self):
        self.media_process.kill()

class Syllable:
    def __init__(self, string, start=0.0, end=0.0):
        self.string = string
        self.start = start
        self.end = end

    def seconds_repr(self, f):
        abssec = int(f)
        msec = int((f - abssec) * 100)
        sec = abssec % 60
        minutes = abssec // 60
        return "[{:02d}:{:02d}.{:02d}]".format(minutes, sec, msec)

    def __str__(self):
        return self.string

    def lrc(self):
        return "{}{}{}".format(self.seconds_repr(self.start), self.string,
                self.seconds_repr(self.end))

class Lyrics:
    def __init__(self, lyricfile):
        with open(lyricfile, 'r') as f:
            self.lyrics = f.readlines()
        segmentcount = 0
        segments = [[]]
        for line in self.lyrics:
            if line == "\n":
                segmentcount += 1
                segments.append([])            
            else:
                segments[segmentcount].append(line[:-1])
        words = [[line.split(" ") for line in segment] for segment in
                segments]
        self._lyrics = [[[[Syllable(syllable) for syllable in word.split("|")] for word in line] for line
                in segment] for segment in words]

    def update_start(self, seg, line, word, syl, time):
        self._lyrics[seg][line][word][syl].start = time

    def update_end(self, seg, line, word, syl, time):
        self._lyrics[seg][line][word][syl].end = time

    def word_flatten(self, stringlist):
        return [''.join([str(syl) for syl in word]) for word in stringlist]
    
    def get_line_before(self, seg, line, word, syl):
        pastline = self.word_flatten(self._lyrics[seg][line][:word])
        pastline.append(''.join([str(s) for s in self._lyrics[seg][line][word][:syl]]))
        return pastline
        
    def get_line_after(self, seg, line, word, syl):
        futureline = [''.join([str(s) for s in self._lyrics[seg][line][word][syl:]])]
        futureline += self.word_flatten(self._lyrics[seg][line][word + 1:])
        return futureline

    def get_line2(self, seg, lin, wor, syl):
        seg, lin, wor, syl = self.inc_counter(seg, lin, wor, syl)
        if wor == 0 and syl == 0 and lin > 0:
            pastline = self.word_flatten(self._lyrics[seg][lin - 1])
        elif wor == 0 and syl == 0 and lin == 0 and seg > 0:
            pastline = self.word_flatten(self._lyrics[seg - 1][-1])
        else:
            pastline = self.get_line_before(seg, lin, wor, syl)
        futureline = self.get_line_after(seg, lin, wor, syl)
        endl = ''
        nl = '\r'
        if wor == 0 and syl == 0 and not (seg == 0 and lin == 0):
            endl = '\n'

        return nl + "\033[1m" + " ".join(pastline) + endl + "\033[90m" + \
                " ".join(futureline) + "\033[0m"

    def inc_counter(self, seg, lin, wor, syl):
        syl += 1
        if syl >= len(self._lyrics[seg][lin][wor]):
            syl = 0
            wor += 1
            if wor >= len(self._lyrics[seg][lin]):
                wor = 0
                lin += 1
                if lin >= len(self._lyrics[seg]):
                    lin = 0
                    seg += 1
                    if seg >= len(self._lyrics):
                        seg = len(self._lyrics) - 1
                        lin = len(self._lyrics[seg]) - 1
                        wor = len(self._lyrics[seg][lin]) - 1
                        syl = len(self._lyrics[seg][lin][wor]) - 1
        return seg, lin, wor, syl


def main(lyricfile, musicfile, outputfile, starttime):
    player = PlayerThread(musicfile, starttime)
    player.start()

    lyrics = Lyrics(lyricfile)
    oldseg = 0
    oldlin = 0
    oldwor = 0
    oldsyl = -1
    seg = 0
    lin = 0
    wor = 0
    syl = 0

    musical_break = False

    while True:
        key = readchar.readkey()
        if key == "q":
            player.kill()
            sys.exit(0)
        elif key == "p":
            player.toggle()
        elif key == " ":
            time = player.gettime()
            seg, lin, wor, syl = lyrics.inc_counter(oldseg, oldlin, oldwor, oldsyl)
            if not musical_break:
                lyrics.update_end(oldseg, oldlin, oldwor, oldsyl, time)
            lyrics.update_start(seg, lin, wor, syl, time)
            sys.stdout.flush()
            print(lyrics.get_line2(seg, lin, wor, syl), end='')
            oldseg, oldlin, oldwor, oldsyl = seg, lin, wor, syl
            musical_break = False
        elif key == "b":
            time = player.gettime()
            lyrics.update_end(seg, lin, wor, syl, time)
            musical_break = True
        elif key == "s":
            with open(outputfile, 'w') as f:
                for segment in lyrics._lyrics:
                    for line in segment:
                        strline = " ".join([''.join([syl.lrc() for syl in word]) for word in line])
                        f.write(strline + "\n")
                    f.write("\n")
        else:
            pass



if __name__ == "__main__":
    parser = ArgumentParser(description = "Sync lyrics to music")
    parser.add_argument("-l", "--lyricsfile", required=True)
    parser.add_argument("-m", "--musicfile", required=True)
    parser.add_argument("-s", "--starttime", type=int, required=True) 
    parser.add_argument("-o", "--outputfile")
    args = parser.parse_args()

    main(args.lyricsfile, args.musicfile, args.outputfile, args.starttime)

